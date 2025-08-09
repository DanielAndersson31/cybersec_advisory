"""
Search for threat intelligence reports (Pulses) on AlienVault OTX.
"""

import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import httpx
from config.settings import settings

logger = logging.getLogger(__name__)


# Pydantic Models
class ThreatPulse(BaseModel):
    """
    Represents a single threat intelligence report (a "Pulse") from AlienVault OTX.
    A Pulse is a collection of indicators of compromise (IOCs) and context about a threat.
    """
    id: str
    name: str
    description: str
    modified: str
    author: str
    tags: List[str] = []


class ThreatFeedResponse(BaseModel):
    """The structured response model for a threat feed search."""
    status: str = "success"
    query: str
    total_results: int
    results: List[ThreatPulse]
    error: Optional[str] = None


class ThreatFeedsTool:
    """Tool for searching threat intelligence feeds via AlienVault OTX"""

    def __init__(self):
        """Initialize OTX client"""
        self.otx_api_key = settings.otx_api_key
        if not self.otx_api_key:
            raise ValueError("OTX_API_KEY not configured in settings")
        self.base_url = "https://otx.alienvault.com/api/v1"
        self.client = httpx.AsyncClient()

    async def search(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """
        Search for threat pulses on AlienVault OTX.
        
        Args:
            query: The search term (e.g., a malware family, threat actor, or campaign name).
            limit: The maximum number of results to return.
            
        Returns:
            A ThreatFeedResponse object containing the search results.
        """
        if not self.otx_api_key:
            return ThreatFeedResponse(
                status="error",
                query=query,
                total_results=0,
                results=[],
                error="OTX_API_KEY is not configured."
            )

        headers = {"X-OTX-API-KEY": self.otx_api_key}
        params = {"q": query, "limit": min(limit, 50)}
        search_url = f"{self.base_url}/search/pulses"

        try:
            # Make the API request
            api_response = await self.client.get(search_url, headers=headers, params=params)
            
            if api_response.status_code != 200:
                return ThreatFeedResponse(
                    status="error",
                    query=query,
                    total_results=0,
                    results=[],
                    error=f"OTX API error: {api_response.status_code} - {api_response.text}"
                )
            
            # Parse the results
            data = api_response.json()
            pulses_data = data.get("results", [])
            
            pulse_results = []
            for pulse in pulses_data:
                pulse_result = ThreatPulse(
                    id=pulse.get("id", ""),
                    name=pulse.get("name", "No name provided"),
                    description=pulse.get("description", "No description provided.")[:300] + "...",
                    modified=pulse.get("modified", ""),
                    author=pulse.get("author_name", "Unknown author"),
                    tags=pulse.get("tags", [])
                )
                pulse_results.append(pulse_result)
            
            return ThreatFeedResponse(
                query=query,
                total_results=len(pulse_results),
                results=pulse_results
            )
                
        except Exception as e:
            logger.error(f"Threat feed search error: {str(e)}")
            return ThreatFeedResponse(
                status="error",
                query=query,
                total_results=0,
                results=[],
                error=str(e)
            )

# Create a singleton instance of the tool, matching the other files
threat_feeds_tool = ThreatFeedsTool()


# Export function that the MCP server will import
async def search_threat_feeds(**kwargs) -> dict:
    """
    Searches AlienVault OTX for threat intelligence reports (Pulses).
    This function is the entry point for the MCP server.
    """
    response = await threat_feeds_tool.search(**kwargs)
    return response.model_dump()