#!/usr/bin/env python3
"""
Knowledge search tool for the cybersecurity multi-agent advisory system.
This tool performs semantic search against a Qdrant vector database.
"""

from typing import Dict, Any, List, Optional
import logging
from pydantic import BaseModel
from langchain_core.tools import BaseTool
import asyncio

# Use lazy import to avoid circular dependency
# from knowledge.knowledge_retrieval import knowledge_retriever

logger = logging.getLogger(__name__)


class KnowledgeResult(BaseModel):
    """A single result from a knowledge base search."""
    doc_id: str
    content: str
    metadata: Dict[str, Any]
    score: float

class KnowledgeSearchResponse(BaseModel):
    """The structured response for a knowledge search query."""
    status: str = "success"
    query: str
    domain_searched: Optional[str] = None
    results: List[KnowledgeResult]
    error: Optional[str] = None


class KnowledgeSearchTool(BaseTool):
    """A tool for performing semantic search on the cybersecurity knowledge base."""
    name: str = "knowledge_search"
    description: str = "Search the internal knowledge base for company policies, playbooks, and documentation."

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
        Search the cybersecurity knowledge base for relevant documents.
        If no domain is specified, it searches across all available domains.

        Args:
            query: The search query string.
            domain: The specific knowledge domain (collection) to search within.
            limit: The maximum number of results to return.

        Returns:
            A KnowledgeSearchResponse object.
        """
        try:
            # Lazy import to avoid circular dependency
            from knowledge.knowledge_retrieval import knowledge_retriever
            
            domains_to_search = []
            if domain:
                domains_to_search.append(domain)
                logger.info(f"Searching knowledge base in specified domain '{domain}' for: '{query}'")
            else:
                # If no domain is specified, search all available collections
                domains_to_search = await knowledge_retriever.store_manager.get_all_collection_names()
                logger.info(f"Searching across all domains for: '{query}'")
            
            if not domains_to_search:
                return KnowledgeSearchResponse(
                    status="info", 
                    query=query, 
                    results=[], 
                    error="Knowledge base not yet populated. No collections available to search."
                )

            # Concurrently search all specified domains
            search_tasks = [
                knowledge_retriever.search(query=query, domain=d, k=limit)
                for d in domains_to_search
            ]
            all_results_nested = await asyncio.gather(*search_tasks)

            # Flatten the list of lists and add domain info to each result
            all_results = []
            for domain_name, results_list in zip(domains_to_search, all_results_nested):
                for result in results_list:
                    result['metadata']['domain'] = domain_name
                    all_results.append(result)

            # Sort all results by score (highest first) and take the top 'limit'
            all_results.sort(key=lambda x: x["score"], reverse=True)
            top_results = all_results[:limit]
            
            # ---> FIX: If no results in specific domain, fallback to all domains <---
            if not top_results and domain and len(domains_to_search) == 1:
                logger.warning(f"No results found in '{domain}'. Falling back to search all domains.")
                # Clear the specific domain and re-run the search across all collections
                return await self.search(query=query, domain=None, limit=limit)

            # Format results into our Pydantic model
            formatted_results = [KnowledgeResult(**result) for result in top_results]

            # Provide helpful status based on results
            status = "success" if formatted_results else "no_results"
            error_msg = None if formatted_results else "No relevant documents found in knowledge base. Consider using web search for current information."

            return KnowledgeSearchResponse(
                status=status,
                query=query,
                domain_searched=domain if domain else "all",
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