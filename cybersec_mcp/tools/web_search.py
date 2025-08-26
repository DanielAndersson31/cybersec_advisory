"""
Web search tool using Tavily API with LLM-enhanced query optimization.
"""

from typing import List, Optional
from pydantic import BaseModel, Field, ValidationError, ConfigDict
from tavily import AsyncTavilyClient
import logging
from config.settings import settings
import instructor
from openai import AsyncOpenAI
from langchain_core.tools import BaseTool
import asyncio


logger = logging.getLogger(__name__)


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
    results: List[WebSearchResult] = Field(description="List of search results")
    total_results: int = Field(ge=0, description="Total number of results returned")
    error: Optional[str] = Field(default=None, description="Error message if search failed")


class WebSearchTool(BaseTool):
    """Web search tool with LLM-enhanced query optimization."""
    name: str = "web_search"
    description: str = "Search the web with LLM-enhanced query optimization for better results."
    tavily: AsyncTavilyClient = None
    instructor: AsyncOpenAI = None

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    def __init__(self, llm_client: AsyncOpenAI, **data):
        super().__init__(**data)
        """Initialize Tavily and Instructor clients."""
        self.tavily = AsyncTavilyClient(api_key=settings.get_secret("tavily_api_key"))
        self.instructor = instructor.patch(llm_client)

    def _run(
        self,
        query: str,
        max_results: int = 5
    ) -> WebSearchResponse:
        """Search the web with LLM-enhanced query crafting."""
        return asyncio.run(self.search(query, max_results))

    async def _arun(
        self,
        query: str,
        max_results: int = 5
    ) -> WebSearchResponse:
        """Search the web with LLM-enhanced query crafting."""
        return await self.search(query, max_results)

    async def _craft_search_query(self, user_query: str) -> str:
        """
        Use LLM to craft better search terms for optimal results.
        """
        try:
            # Simple prompt to enhance search queries
            messages = [
                {
                    "role": "system",
                    "content": """You are a search query optimization expert. Your job is to take a user's query and create the best possible search terms for web search engines.

Guidelines:
- Keep it concise but specific
- Add relevant keywords that would help find better results
- Remove unnecessary words and filler
- For technical topics, include proper terminology
- For current/latest information, use "current", "latest", "recent", "today" - NEVER add specific years unless the user explicitly asks for historical data
- For locations, include geographic specifics if helpful
- Preserve the user's intent - don't change the meaning

Examples:
User: "What's the weather like in London?"
Enhanced: "London weather current conditions today"

User: "How to install Docker?"
Enhanced: "Docker installation guide setup tutorial"

User: "NIST framework"
Enhanced: "NIST Cybersecurity Framework guide implementation"

User: "Latest ransomware attack"
Enhanced: "latest ransomware attack cybersecurity news recent"

User: "current day and date"
Enhanced: "current date today"

User: "DDoS prevention strategies"
Enhanced: "DDoS attack prevention strategies latest methods"

IMPORTANT: Never add specific years (like 2023, 2024) unless the user specifically asks for historical information from a particular year.

Return ONLY the enhanced search query, nothing else."""
                },
                {
                    "role": "user",
                    "content": f"Enhance this search query: {user_query}"
                }
            ]

            # Use instructor-patched client directly for simple string response
            response = await self.instructor.chat.completions.create(
                model=settings.default_model,  # Use default model since search_model_name might not exist
                messages=messages,
                max_tokens=100,
                temperature=0.1
            )
            
            enhanced = response.choices[0].message.content
            return enhanced.strip() if enhanced else user_query
            
        except Exception as e:
            logger.warning(f"Query enhancement failed: {e}, using original query")
            return user_query

    async def search(
        self,
        query: str,
        max_results: int = 5
    ) -> WebSearchResponse:
        """
        Search the web with LLM-enhanced query crafting.
        
        Args:
            query: User's search query
            max_results: Maximum number of results (1-10)
            
        Returns:
            A WebSearchResponse object.
        """
        # Validate and limit results
        max_results = min(max_results, 10)
        
        try:
            # Use LLM to craft better search terms
            enhanced_query = await self._craft_search_query(query)
            logger.info(f"Original query: '{query}' → Enhanced: '{enhanced_query}'")
            
            results = await self.tavily.search(
                query=enhanced_query,
                max_results=max_results,
                search_depth="basic"
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
                results=formatted_results,
                total_results=len(formatted_results)
            )
            
            # Log result quality
            if len(formatted_results) == 0:
                logger.warning(f"No results found for enhanced query: {enhanced_query}")
            
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