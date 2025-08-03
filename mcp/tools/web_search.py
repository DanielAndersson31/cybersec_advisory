"""
Web search tool using Tavily API for cybersecurity queries.
"""

import os
from typing import Dict, Any, List, Optional
from tavily import TavilyClient
import logging

logger = logging.getLogger(__name__)


class WebSearchTool:
    """Web search tool using Tavily API"""
    
    def __init__(self):
        """Initialize Tavily client"""
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            raise ValueError("TAVILY_API_KEY environment variable not set")
            
        self.client = TavilyClient(api_key=api_key)
        
        # Trusted cybersecurity domains
        self.trusted_domains = [
            "cisa.gov",
            "nist.gov",
            "mitre.org",
            "sans.org",
            "bleepingcomputer.com",
            "krebsonsecurity.com"
        ]
    
    async def search(
        self,
        query: str,
        max_results: int = 5,
        search_type: str = "general",
        include_domains: Optional[List[str]] = None,
        time_range: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search the web for cybersecurity information.
        
        Args:
            query: Search query string
            max_results: Maximum number of results (1-10)
            search_type: Type of search - 'general', 'news', or 'research'
            include_domains: Optional list of domains to search within
            time_range: Filter by time - 'day', 'week', 'month', 'year'
            
        Returns:
            Dict containing search results
        """
        # Validate and limit results
        max_results = min(max_results, 10)
        
        # Enhance query for cybersecurity context
        enhanced_query = self._enhance_query(query, search_type)
        
        # Convert time range to days
        days = None
        if time_range:
            time_map = {"day": 1, "week": 7, "month": 30, "year": 365}
            days = time_map.get(time_range)
        
        # Use trusted domains if none specified for general search
        if not include_domains and search_type == "general":
            include_domains = self.trusted_domains
        
        try:
            # Call Tavily API
            logger.info(f"Searching for: {enhanced_query}")
            
            results = self.client.search(
                query=enhanced_query,
                max_results=max_results,
                search_depth="basic" if search_type != "research" else "advanced",
                include_domains=include_domains,
                days=days
            )
            
            # Format results
            formatted_results = []
            for result in results.get("results", []):
                formatted_results.append({
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "content": result.get("content", ""),
                    "score": result.get("score", 0.0),
                    "published_date": result.get("published_date")
                })
            
            return {
                "status": "success",
                "query": query,
                "enhanced_query": enhanced_query,
                "results": formatted_results,
                "total_results": len(formatted_results)
            }
            
        except Exception as e:
            logger.error(f"Search error: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "query": query,
                "results": []
            }
    
    def _enhance_query(self, query: str, search_type: str) -> str:
        """Add cybersecurity context to query if needed"""
        # Don't enhance if already has cyber terms
        cyber_terms = ["cyber", "security", "malware", "vulnerability", "CVE"]
        if any(term.lower() in query.lower() for term in cyber_terms):
            return query
            
        # Enhance based on search type
        if search_type == "general":
            return f"cybersecurity {query}"
        elif search_type == "news":
            return f"cybersecurity news {query} 2025"
        elif search_type == "research":
            return f"cybersecurity research {query}"
        
        return query


# Create singleton instance
web_search_tool = WebSearchTool()


# Export function for easy use
async def web_search(**kwargs) -> Dict[str, Any]:
    """Web search function that MCP servers will import"""
    return await web_search_tool.search(**kwargs)