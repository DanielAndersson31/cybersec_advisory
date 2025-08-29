"""
Web search tool using Tavily API with LLM-enhanced query optimization and proper time filtering.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ValidationError, ConfigDict
from tavily import AsyncTavilyClient
import logging
from config.settings import settings
import instructor
from openai import AsyncOpenAI
from langchain_core.tools import BaseTool
import asyncio
from datetime import datetime, timedelta
import re

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
    time_filter_applied: Optional[str] = Field(default=None, description="Time filter that was applied")
    error: Optional[str] = Field(default=None, description="Error message if search failed")


class WebSearchTool(BaseTool):
    """Web search tool with LLM-enhanced query optimization and proper time filtering."""
    name: str = "web_search"
    description: str = "Search the web with LLM-enhanced query optimization and time filtering for current results."
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

    def _detect_temporal_intent(self, query: str) -> Dict[str, Any]:
        """
        Detect temporal intent in the query and return appropriate Tavily parameters.
        """
        query_lower = query.lower()
        logger.debug(f"Detecting temporal intent for query: '{query}'")
        
        # TIME QUERIES - These CAN use web search but need special handling
        time_keywords = ['time', 'clock', 'timezone', 'what time is it']
        if any(keyword in query_lower for keyword in time_keywords):
            logger.debug(f"Time query detected! Keywords found: {[k for k in time_keywords if k in query_lower]}")
            return {
                'temporal_detected': 'time_query', 
                'topic': 'general',
                'special_handling': 'time',
                'preserve_query': True  # Don't let LLM remove temporal keywords
            }
        
        # Define temporal keywords and their corresponding time ranges
        temporal_patterns = {
            'today': {'time_range': 'day', 'topic': 'general'},
            'latest': {'time_range': 'week', 'topic': 'general'},
            'recent': {'time_range': 'week', 'topic': 'general'},
            'breaking': {'time_range': 'day', 'topic': 'news'},
            'news': {'time_range': 'day', 'topic': 'news'},
            'this week': {'time_range': 'week', 'topic': 'general'},
            'this month': {'time_range': 'month', 'topic': 'general'},
            'this year': {'time_range': 'year', 'topic': 'general'},
        }
        
        # Weather queries should always be current
        if any(word in query_lower for word in ['weather', 'temperature', 'forecast', 'climate']):
            return {'time_range': 'day', 'topic': 'general', 'temporal_detected': 'weather', 'preserve_query': True}
        
        # Stock/financial queries should be current  
        if any(word in query_lower for word in ['stock', 'price', 'market', 'trading', 'exchange rate']):
            return {'time_range': 'day', 'topic': 'finance', 'temporal_detected': 'financial', 'preserve_query': True}
        
        # CURRENT/NOW - apply temporal filtering
        if 'current' in query_lower or 'now' in query_lower:
            return {'time_range': 'day', 'topic': 'general', 'temporal_detected': 'current'}
        
        # Check for explicit temporal keywords
        for pattern, params in temporal_patterns.items():
            if pattern in query_lower:
                params['temporal_detected'] = pattern
                return params
        
        # Check for date patterns (but don't add them - user specified dates)
        date_pattern = re.search(r'\b(20\d{2})\b', query_lower)
        if date_pattern:
            year = date_pattern.group(1)
            # If it's a recent year, use time range
            current_year = datetime.now().year
            if int(year) >= current_year - 1:
                return {'time_range': 'year', 'topic': 'general', 'temporal_detected': f'year_{year}'}
        
        return {'temporal_detected': None}

    async def _craft_search_query(self, user_query: str, preserve_query: bool = False) -> str:
        """
        Use LLM to craft better search terms for optimal results.
        """
        try:
            logger.debug(f"Crafting search query. Original: '{user_query}', preserve_query: {preserve_query}")
            
            # If preserve_query is True (for time queries), use original query
            if preserve_query:
                logger.debug(f"Preserving original query for time-sensitive search")
                return user_query
                
            # Remove any years from the query before LLM sees it - let temporal parameters handle time filtering
            cleaned_query = re.sub(r'\b(20\d{2})\b', '', user_query).strip()

            # Simple prompt to enhance search queries
            messages = [
                {
                    "role": "system",
                    "content": """You are a search query optimization expert. Your job is to take a user's query and create the best possible search terms for web search engines.

Guidelines:
- Keep it concise but specific (under 50 words)
- Add relevant keywords that would help find better results
- Remove unnecessary words and filler
- For technical topics, include proper terminology
- Do NOT add temporal words like "today", "current", "latest", "recent" - the system handles time filtering separately
- ABSOLUTELY DO NOT add any specific dates or years - time filtering is handled by other parameters
- Focus on the core topic and relevant keywords only

Examples:
User: "What's the latest news about Tesla?"
Enhanced: "Tesla news updates developments"

User: "Current weather in London"
Enhanced: "London weather conditions"

User: "Recent developments in AI"
Enhanced: "artificial intelligence developments progress research"

Return ONLY the enhanced search query focused on the main topic, nothing else."""
                },
                {
                    "role": "user",
                    "content": f"Enhance this search query by focusing on the main topic: {cleaned_query}"
                }
            ]

            response = await self.instructor.chat.completions.create(
                model=settings.default_model,
                messages=messages,
                max_tokens=100,
                temperature=0.1
            )
            
            enhanced = response.choices[0].message.content
            return enhanced.strip() if enhanced else cleaned_query
            
        except Exception as e:
            logger.warning(f"Query enhancement failed: {e}, using original query")
            return user_query

    async def search(
        self,
        query: str,
        max_results: int = 5
    ) -> WebSearchResponse:
        """
        Search the web with LLM-enhanced query crafting and proper time filtering.
        
        Args:
            query: User's search query
            max_results: Maximum number of results (1-10)
            
        Returns:
            A WebSearchResponse object.
        """
        # Validate and limit results
        max_results = min(max_results, 10)
        
        try:
            # Detect temporal intent and get appropriate parameters
            temporal_params = self._detect_temporal_intent(query)
            logger.info(f"Temporal detection for '{query}': {temporal_params}")
            
            # Use LLM to craft better search terms (preserve original for time queries)
            preserve_query = temporal_params.get('preserve_query', False)
            enhanced_query = await self._craft_search_query(query, preserve_query)
            logger.info(f"Original query: '{query}' → Enhanced query: '{enhanced_query}'")
            
            # Build search parameters
            search_params = {
                "query": enhanced_query,
                "max_results": max_results,
                "search_depth": "basic"
            }
            
            # Add temporal parameters if detected
            time_filter_applied = []
            if temporal_params.get('temporal_detected'):
                if 'time_range' in temporal_params:
                    search_params['time_range'] = temporal_params['time_range']
                    time_filter_applied.append(f"time_range: {temporal_params['time_range']}")
                
                if 'topic' in temporal_params:
                    search_params['topic'] = temporal_params['topic']
                    time_filter_applied.append(f"topic: {temporal_params['topic']}")
                
                # Add domain filtering for time queries
                if 'include_domains' in temporal_params:
                    search_params['include_domains'] = temporal_params['include_domains']
                    time_filter_applied.append(f"include_domains: {temporal_params['include_domains']}")
                
                # Add special handling marker
                if 'special_handling' in temporal_params:
                    time_filter_applied.append(f"special_handling: {temporal_params['special_handling']}")
                
                # For news queries, also add days parameter for more precision
                if temporal_params.get('topic') == 'news' and 'time_range' in temporal_params:
                    if temporal_params.get('time_range') == 'day':
                        search_params['days'] = 1
                    elif temporal_params.get('time_range') == 'week':
                        search_params['days'] = 7
                    
                    if 'days' in search_params:
                        time_filter_applied.append(f"days: {search_params['days']}")
                
                logger.info(f"Applied parameters: {', '.join(time_filter_applied)}")
            
            # Execute search with parameters
            logger.debug(f"Sending to Tavily API with params: {search_params}")
            results = await self.tavily.search(**search_params)

            # ---> FIX: If basic search fails, retry with advanced search <---
            if not results.get("results"):
                logger.warning("Basic search returned no results. Retrying with advanced search.")
                search_params["search_depth"] = "advanced"
                results = await self.tavily.search(**search_params)
                logger.info("Advanced search completed after basic search failed.")

            logger.debug(f"Raw Tavily response keys: {list(results.keys()) if isinstance(results, dict) else 'Not a dict'}")
            logger.debug(f"Raw Tavily response: {results}")
            
            # Format results with validation
            formatted_results = []
            raw_results = results.get("results", [])
            logger.debug(f"Found {len(raw_results)} raw results from Tavily")
            
            for i, result in enumerate(raw_results):
                logger.debug(f"Processing result {i+1}:")
                logger.debug(f"  - Title: {result.get('title', 'NO TITLE')}")
                logger.debug(f"  - URL: {result.get('url', 'NO URL')}")
                logger.debug(f"  - Content preview: {result.get('content', 'NO CONTENT')[:100]}...")
                logger.debug(f"  - Score: {result.get('score', 'NO SCORE')}")
                logger.debug(f"  - Published date: {result.get('published_date', 'NO DATE')}")
                
                try:
                    formatted_result = WebSearchResult(
                        title=result.get("title", ""),
                        url=result.get("url", ""),
                        content=result.get("content", ""),
                        score=max(0.0, float(result.get("score", 0.0))),
                        published_date=result.get("published_date")
                    )
                    formatted_results.append(formatted_result)
                    logger.debug(f"Successfully formatted result {i+1}")
                except ValidationError as e:
                    logger.warning(f"Skipping invalid search result {i+1}: {e}")
                    continue
            
            response = WebSearchResponse(
                query=query,
                enhanced_query=enhanced_query,
                results=formatted_results,
                total_results=len(formatted_results),
                time_filter_applied=', '.join(time_filter_applied) if time_filter_applied else None
            )
            
            # Log result quality
            if len(formatted_results) == 0:
                logger.warning(f"No results found for enhanced query: {enhanced_query}")
            else:
                logger.info(f"Found {len(formatted_results)} results with filters: {', '.join(time_filter_applied)}")
            
            logger.debug(f"Final response summary:")
            logger.debug(f"  - Original query: '{response.query}'")
            logger.debug(f"  - Enhanced query: '{response.enhanced_query}'")
            logger.debug(f"  - Time filters: '{response.time_filter_applied}'")
            logger.info(f"  - Total results: {response.total_results}")
            logger.info(f"  - Status: '{response.status}'")
            
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