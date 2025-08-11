"""
Web search tool using Tavily API for cybersecurity queries.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from tavily import AsyncTavilyClient
import logging
from config.settings import settings
import instructor
from openai import AsyncOpenAI
from async_lru import alru_cache


logger = logging.getLogger(__name__)


class QueryIntent(BaseModel):
    """The classified intent of a user's search query."""
    is_cybersecurity: bool
    confidence: float
    reasoning: str
    suggested_enhancement: Optional[str] = None


class WebSearchResult(BaseModel):
    """A single web search result."""
    title: str
    url: str
    content: str
    score: float
    published_date: Optional[str] = None

class WebSearchResponse(BaseModel):
    """The structured response for a web search query."""
    status: str = "success"
    query: str
    enhanced_query: str
    intent_reasoning: Optional[str] = None  # Add reasoning for transparency
    results: List[WebSearchResult]
    total_results: int
    error: Optional[str] = None


class WebSearchTool:
    """Web search tool using Tavily API and LLM-based intent classification."""
    
    def __init__(self):
        """Initialize Tavily and Instructor clients."""
        self.tavily = AsyncTavilyClient(api_key=settings.get_secret("tavily_api_key"))
        
        self.instructor = instructor.patch(
            AsyncOpenAI(api_key=settings.get_secret("openai_api_key"))
        )
        
        # A curated list of authoritative domains for high-quality results.
        self.trusted_domains = [
            # Threat Intelligence & News
            "bleepingcomputer.com",
            "darkreading.com",
            "thehackernews.com",
            "threatpost.com",
            "krebsonsecurity.com",
            
            # Vulnerability & Standards Databases
            "cve.mitre.org",
            "nvd.nist.gov",
            "owasp.org",

            # Government & Research Organizations
            "cisa.gov",
            "us-cert.gov",
            "sans.org",

            # Leading Security Vendor Blogs (can be adjusted)
            "fireeye.com/blog",
            "crowdstrike.com/blog",
            "mandiant.com/resources/blog"
        ]

    @alru_cache(maxsize=128)
    async def classify_query_intent(self, query: str) -> QueryIntent:
        """
        Use an LLM to classify if the query is cybersecurity-related.
        This method is cached to improve performance for repeated queries.
        """
        try:
            # This prompt guides the LLM to return structured JSON.
            return await self.instructor.chat.completions.create(
                model=settings.search_model_name,
                response_model=QueryIntent,
                messages=[
                    {"role": "system", "content": "You are a world-class cybersecurity expert. Your task is to classify search queries."},
                    {"role": "user", "content": f"Analyze this query and determine if it's related to cybersecurity, IT security, or information security.\nQuery: '{query}'"}
                ]
            )
        except Exception as e:
            logger.error(f"Intent classification LLM error: {e}")
            # Fallback to a safe default
            return QueryIntent(
                is_cybersecurity=False, 
                confidence=0.0, 
                reasoning=f"LLM classification failed: {e}"
            )

    async def search(
        self,
        query: str,
        max_results: int = 5,
        search_type: str = "general",
        include_domains: Optional[List[str]] = None,
        time_range: Optional[str] = None
    ) -> WebSearchResponse:
        """
        Search the web for cybersecurity information.
        
        Args:
            query: Search query string
            max_results: Maximum number of results (1-10)
            search_type: Type of search - 'general', 'news', or 'research'
            include_domains: Optional list of domains to search within
            time_range: Filter by time - 'd' (day), 'w' (week), 'm' (month), 'y' (year)
            
        Returns:
            A WebSearchResponse object.
        """
        # Validate and limit results
        max_results = min(max_results, 10)
        
        # Classify intent to determine if enhancement is needed.
        intent = await self.classify_query_intent(query)
        logger.info(f"Query intent classified: {intent.model_dump_json(indent=2)}")

        enhanced_query = query
        # Only enhance if the LLM is confident it's a cybersecurity query.
        if intent.is_cybersecurity and intent.confidence >= settings.search_confidence_threshold:
            enhanced_query = intent.suggested_enhancement or self._enhance_query(query, search_type)
        
        # For cybersecurity searches, use trusted domains if none are specified.
        # For general queries, search the whole web unless specific domains are provided.
        search_domains = include_domains
        if (
            not search_domains and 
            search_type == "general" and 
            intent.is_cybersecurity and 
            intent.confidence >= settings.search_confidence_threshold
        ):
            search_domains = self.trusted_domains
        
        try:
            # Call Tavily API with the potentially enhanced query.
            logger.info(f"Searching for: '{enhanced_query}' within domains: {search_domains or 'any'}")
            
            results = await self.tavily.search(
                query=enhanced_query,
                max_results=max_results,
                search_depth="basic" if search_type != "research" else "advanced",
                include_domains=search_domains,
                time_range=time_range
            )
            
            # Format results
            formatted_results = []
            for result in results.get("results", []):
                formatted_results.append(WebSearchResult(
                    title=result.get("title", ""),
                    url=result.get("url", ""),
                    content=result.get("content", ""),
                    score=result.get("score", 0.0),
                    published_date=result.get("published_date")
                ))
            
            return WebSearchResponse(
                query=query,
                enhanced_query=enhanced_query,
                intent_reasoning=intent.reasoning,
                results=formatted_results,
                total_results=len(formatted_results)
            )
            
        except Exception as e:
            logger.error(f"Search error: {str(e)}")
            return WebSearchResponse(
                status="error",
                query=query,
                enhanced_query=query, # Use original query on error
                results=[],
                total_results=0,
                error=str(e)
            )
    
    def _enhance_query(self, query: str, search_type: str) -> str:
        """Provides a fallback enhancement for confirmed cybersecurity queries."""
        prefix = "cybersecurity"
        if search_type == "news":
            # For news, adding a year can help focus results on recent events.
            return f"{prefix} news {query} 2025"
        elif search_type == "research":
            return f"{prefix} research paper {query}"
        
        return f"{prefix} {query}"


# Create singleton instance
web_search_tool = WebSearchTool()


# Export function for easy use
async def web_search(**kwargs) -> Dict[str, Any]:
    """Web search function that MCP servers will import"""
    response = await web_search_tool.search(**kwargs)
    return response.model_dump()