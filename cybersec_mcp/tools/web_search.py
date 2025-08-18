"""
Web search tool using Tavily API for cybersecurity queries.
"""

from typing import Dict, Any, List, Optional, Literal
from pydantic import BaseModel, Field, ValidationError
from tavily import AsyncTavilyClient
import logging
from config.settings import settings
import instructor
from openai import AsyncOpenAI
from async_lru import alru_cache


logger = logging.getLogger(__name__)


class QueryIntent(BaseModel):
    """The classified intent of a user's search query."""
    is_cybersecurity: bool = Field(description="Whether the query is cybersecurity-related")
    confidence: float = Field(
        ge=0.0, le=1.0, 
        description="Confidence score between 0 and 1"
    )
    reasoning: str = Field(
        max_length=500,
        description="Brief explanation of the classification"
    )
    category: Optional[Literal[
        "threat_intelligence", "vulnerability", "compliance", 
        "incident_response", "security_tools", "general_security", "non_security"
    ]] = Field(description="Specific cybersecurity category if applicable")
    suggested_enhancement: Optional[str] = Field(
        max_length=200,
        description="Enhanced query for better search results"
    )


class WebSearchResult(BaseModel):
    """A single web search result."""
    title: str = Field(description="Title of the search result")
    url: str = Field(description="URL of the search result")
    content: str = Field(description="Content snippet from the search result")
    score: float = Field(ge=0.0, description="Relevance score")
    published_date: Optional[str] = Field(description="Publication date if available")


class WebSearchResponse(BaseModel):
    """The structured response for a web search query."""
    status: str = Field(default="success", description="Status of the search operation")
    query: str = Field(description="Original search query")
    enhanced_query: str = Field(description="Enhanced or modified query used for search")
    intent_reasoning: Optional[str] = Field(description="Reasoning for query classification")
    results: List[WebSearchResult] = Field(description="List of search results")
    total_results: int = Field(ge=0, description="Total number of results returned")
    error: Optional[str] = Field(description="Error message if search failed")


class WebSearchTool:
    """Web search tool using Tavily API and LLM-based intent classification."""
    
    SEARCH_CONFIDENCE_THRESHOLD = 0.7

    def __init__(self, llm_client: AsyncOpenAI):
        """Initialize Tavily and Instructor clients."""
        self.tavily = AsyncTavilyClient(api_key=settings.get_secret("tavily_api_key"))
        
        self.instructor = instructor.patch(llm_client)
        
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
            # Enhanced prompt for better classification
            return await self.instructor.chat.completions.create(
                model=settings.search_model_name,
                response_model=QueryIntent,
                max_retries=2,  # Add retry logic for reliability
                messages=[
                    {
                        "role": "system", 
                        "content": """You are a cybersecurity expert who classifies search queries.
                        
                        Analyze if the query relates to:
                        - Cybersecurity threats, vulnerabilities, malware
                        - IT security, information security, data protection
                        - Security tools, frameworks, compliance (SOC2, ISO27001, etc.)
                        - Incident response, forensics, risk management
                        - Network security, endpoint security, cloud security
                        
                        Provide a confidence score and suggest query enhancements for better search results.
                        Be conservative - only mark as cybersecurity if clearly related."""
                    },
                    {
                        "role": "user", 
                        "content": f"""Classify this search query:
                        
                        Query: "{query}"
                        
                        Consider:
                        1. Is this clearly cybersecurity-related?
                        2. What specific category does it fall into?
                        3. How could the query be enhanced for better search results?
                        4. What's your confidence level (0.0 to 1.0)?"""
                    }
                ]
            )
        except ValidationError as e:
            logger.error(f"Validation error in intent classification: {e}")
            # Fallback with proper validation
            return QueryIntent(
                is_cybersecurity=False, 
                confidence=0.0, 
                reasoning=f"Validation failed: {str(e)}",
                category="non_security"
            )
        except Exception as e:
            logger.error(f"Intent classification LLM error: {e}")
            # Fallback to a safe default
            return QueryIntent(
                is_cybersecurity=False, 
                confidence=0.0, 
                reasoning=f"LLM classification failed: {str(e)}",
                category="non_security"
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
        
        try:
            # Classify intent to determine if enhancement is needed.
            intent = await self.classify_query_intent(query)
            logger.info(f"Query intent classified: {intent.model_dump_json(indent=2)}")

            enhanced_query = query
            # Only enhance if the LLM is confident it's a cybersecurity query.
            if intent.is_cybersecurity and intent.confidence >= self.SEARCH_CONFIDENCE_THRESHOLD:
                enhanced_query = intent.suggested_enhancement or self._enhance_query(query, search_type)
            
            # For cybersecurity searches, use trusted domains if none are specified.
            # For general queries, search the whole web unless specific domains are provided.
            search_domains = include_domains
            if (
                not search_domains and 
                search_type == "general" and 
                intent.is_cybersecurity and 
                intent.confidence >= self.SEARCH_CONFIDENCE_THRESHOLD
            ):
                search_domains = self.trusted_domains
            
            # Call Tavily API with the potentially enhanced query.
            logger.info(f"Searching for: '{enhanced_query}' within domains: {search_domains or 'any'}")
            
            results = await self.tavily.search(
                query=enhanced_query,
                max_results=max_results,
                search_depth="basic" if search_type != "research" else "advanced",
                include_domains=search_domains,
                time_range=time_range
            )
            
            # Format results with validation
            formatted_results = []
            for result in results.get("results", []):
                try:
                    formatted_result = WebSearchResult(
                        title=result.get("title", ""),
                        url=result.get("url", ""),
                        content=result.get("content", ""),
                        score=max(0.0, float(result.get("score", 0.0))),  # Ensure non-negative
                        published_date=result.get("published_date")
                    )
                    formatted_results.append(formatted_result)
                except ValidationError as e:
                    logger.warning(f"Skipping invalid search result: {e}")
                    continue
            
            response = WebSearchResponse(
                query=query,
                enhanced_query=enhanced_query,
                intent_reasoning=intent.reasoning,
                results=formatted_results,
                total_results=len(formatted_results)
            )
            
            # Validate response quality
            if len(formatted_results) == 0 and intent.is_cybersecurity:
                logger.warning(f"No results found for cybersecurity query: {query}")
            
            return response
            
        except ValidationError as e:
            logger.error(f"Validation error in search response: {e}")
            return WebSearchResponse(
                status="error",
                query=query,
                enhanced_query=query,
                results=[],
                total_results=0,
                error=f"Validation error: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Search error: {str(e)}")
            return WebSearchResponse(
                status="error",
                query=query,
                enhanced_query=query,
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


# Export function for easy use
async def web_search(**kwargs) -> Dict[str, Any]:
    """Web search function that MCP servers will import"""
    # This function will be called by the MCP server, which will manage the tool instance
    # The tool instance will be created and passed in by the server
    pass