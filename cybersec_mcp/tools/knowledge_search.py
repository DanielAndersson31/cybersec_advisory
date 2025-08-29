#!/usr/bin/env python3
"""
Knowledge search tool for the cybersecurity multi-agent advisory system.
This tool performs semantic search against a Qdrant vector database.
"""

from typing import Any, Optional
import logging
from pydantic import ConfigDict
from langchain_core.tools import BaseTool
import asyncio

from .schemas import KnowledgeResult, KnowledgeSearchResponse

logger = logging.getLogger(__name__)


class KnowledgeSearchTool(BaseTool):
    """A tool for performing semantic search on the cybersecurity knowledge base."""
    name: str = "knowledge_search"
    description: str = "Search the internal knowledge base for company policies, playbooks, and documentation."
    knowledge_retriever: Any = None
    
    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)
    
    def __init__(self, knowledge_retriever=None, **data):
        super().__init__(**data)
        if knowledge_retriever is None:
            # Fallback for backward compatibility - create instance instead of using global
            from knowledge.knowledge_retrieval import create_knowledge_retriever
            self.knowledge_retriever = create_knowledge_retriever()
            logger.warning("KnowledgeSearchTool initialized without dependency injection. Consider passing knowledge_retriever in constructor.")
        else:
            self.knowledge_retriever = knowledge_retriever
            logger.info("KnowledgeSearchTool initialized with proper dependency injection.")

    def _run(
        self,
        query: str,
        domain: Optional[str] = None,
        limit: int = 5,
    ) -> KnowledgeSearchResponse:
        """Search the cybersecurity knowledge base for relevant documents."""
        return asyncio.run(self.search(query, domain, limit))

    async def _arun(
        self,
        query: str,
        domain: Optional[str] = None,
        limit: int = 5,
    ) -> KnowledgeSearchResponse:
        """Search the cybersecurity knowledge base for relevant documents."""
        return await self.search(query, domain, limit)

    async def search(
        self,
        query: str,
        domain: Optional[str] = None,
        limit: int = 5,
    ) -> KnowledgeSearchResponse:
        """
        Optimized search that avoids redundant embedding and searching.
        If a specific domain yields no results, searches remaining domains efficiently.

        Args:
            query: The search query string.
            domain: The specific knowledge domain (collection) to search within.
            limit: The maximum number of results to return.

        Returns:
            A KnowledgeSearchResponse object.
        """
        try:
            # Get all available domains first
            all_available_domains = await self.knowledge_retriever.get_available_domains()
            
            if not all_available_domains:
                return KnowledgeSearchResponse(
                    status="info", 
                    query=query,
                    results=[],
                    error="Knowledge base not yet populated. No collections available to search."
                )

            # Determine search strategy based on domain parameter
            if domain:
                if domain not in all_available_domains:
                    return KnowledgeSearchResponse(
                        status="error",
                        query=query,
                        domain_searched=domain,
                        results=[],
                        error=f"Specified domain '{domain}' does not exist. Available domains: {', '.join(all_available_domains)}"
                    )
                
                # First, search the specific domain
                logger.info(f"Searching knowledge base in specified domain '{domain}' for: '{query}'")
                initial_results = await self.knowledge_retriever.search(query=query, domain=domain, k=limit)
                
                # Add domain info to results
                for result in initial_results:
                    result['metadata']['domain'] = domain
                
                if initial_results:
                    # Got results in the specified domain, return them
                    formatted_results = [KnowledgeResult(**result) for result in initial_results]
                    return KnowledgeSearchResponse(
                        status="success",
                        query=query,
                        domain_searched=domain,
                        results=formatted_results
                    )
                else:
                    # No results in specified domain, search remaining domains
                    logger.warning(f"No results found in '{domain}'. Searching remaining domains efficiently.")
                    remaining_domains = [d for d in all_available_domains if d != domain]
                    domains_to_search = remaining_domains
                    fallback_mode = True
            else:
                # Search all domains
                logger.info(f"Searching across all {len(all_available_domains)} domains for: '{query}'")
                domains_to_search = all_available_domains
                fallback_mode = False

            if not domains_to_search:
                # This shouldn't happen, but handle edge case
                return KnowledgeSearchResponse(
                    status="no_results",
                    query=query,
                    domain_searched=domain or "all",
                    results=[],
                    error="No additional domains to search."
                )

            # Concurrently search all target domains (avoids redundant work)
            search_tasks = [
                self.knowledge_retriever.search(query=query, domain=d, k=limit)
                for d in domains_to_search
            ]
            all_results_nested = await asyncio.gather(*search_tasks)

            # Flatten results and add domain metadata
            all_results = []
            for domain_name, results_list in zip(domains_to_search, all_results_nested):
                for result in results_list:
                    result['metadata']['domain'] = domain_name
                    all_results.append(result)

            # Sort by score (highest first) and take top results
            all_results.sort(key=lambda x: x["score"], reverse=True)
            top_results = all_results[:limit]
            
            # Format results
            formatted_results = [KnowledgeResult(**result) for result in top_results]

            # Determine response status and domain_searched value
            if fallback_mode:
                domain_searched = f"{domain} (fallback to remaining domains)"
            else:
                domain_searched = domain if domain else "all"

            status = "success" if formatted_results else "no_results"
            error_msg = None if formatted_results else "No relevant documents found in knowledge base. Consider using web search for current information."

            return KnowledgeSearchResponse(
                status=status,
                query=query,
                domain_searched=domain_searched,
                results=formatted_results,
                error=error_msg
            )

        except Exception as e:
            logger.error(f"Knowledge search error: {e}", exc_info=True)
            return KnowledgeSearchResponse(
                status="error",
                query=query,
                domain_searched=domain if domain else "all",
                results=[],
                error=f"An unexpected error occurred during the search: {e}",
            )