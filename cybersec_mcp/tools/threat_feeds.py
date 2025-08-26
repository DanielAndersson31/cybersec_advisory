"""
Search for threat intelligence reports (Pulses) on AlienVault OTX.
"""

import logging
from typing import List, Optional, Union
from pydantic import BaseModel, Field, ConfigDict
from langchain_core.tools import BaseTool
import httpx
from config.settings import settings
import asyncio


logger = logging.getLogger(__name__)


# Pydantic Models for structured, validated data
class Indicator(BaseModel):
    """Represents a single Indicator of Compromise (IOC) from a Pulse."""
    indicator: str
    type: str
    title: Optional[str] = ""
    description: Optional[str] = ""

class ThreatPulseSummary(BaseModel):
    """Represents the summary of a threat pulse, returned from a search."""
    id: str
    name: str
    description: Optional[str] = ""
    author_name: str
    modified: str
    tags: List[str] = []

class ThreatPulse(ThreatPulseSummary):
    """
    Represents a single, detailed threat intelligence report (a "Pulse") from AlienVault OTX.
    A Pulse is a collection of indicators of compromise (IOCs) and context about a threat.
    """
    references: List[str] = []
    indicators: List[Indicator] = []
    malware_families: List[str] = []


class ThreatFeedResponse(BaseModel):
    """The structured response model for a threat feed search."""
    status: str = "success"
    query: str
    total_results: int
    results: List[Union[ThreatPulse, ThreatPulseSummary]]
    error: Optional[str] = None


class ThreatFeedsTool(BaseTool):
    """Tool for searching threat intelligence feeds via AlienVault OTX"""
    name: str = "threat_feeds"
    description: str = "Query threat intelligence feeds for information about threat actors, campaigns, or TTPs."
    otx_api_key: str = Field(default_factory=lambda: settings.get_secret("otx_api_key"))
    base_url: str = "https://otx.alienvault.com/api/v1"
    client: httpx.AsyncClient = None

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    def __init__(self, **data):
        super().__init__(**data)
        """Initialize OTX client using centralized secret management."""
        if not self.otx_api_key:
            raise ValueError("OTX_API_KEY is not configured in settings")
        self.client = httpx.AsyncClient(headers={"X-OTX-API-KEY": self.otx_api_key}, timeout=30.0)

    def _run(
        self, 
        query: str, 
        limit: int = 5,
        fetch_full_details: bool = False
    ) -> ThreatFeedResponse:
        """Search for threat pulses on AlienVault OTX."""
        return asyncio.run(self.search(query, limit, fetch_full_details))

    async def _arun(
        self, 
        query: str, 
        limit: int = 5,
        fetch_full_details: bool = False
    ) -> ThreatFeedResponse:
        """Search for threat pulses on AlienVault OTX."""
        return await self.search(query, limit, fetch_full_details)

    async def get_pulse_details(self, pulse_id: str) -> Optional[ThreatPulse]:
        """Fetch the full details for a single threat pulse, including IOCs."""
        detail_url = f"{self.base_url}/pulses/{pulse_id}"
        try:
            response = await self.client.get(detail_url)
            response.raise_for_status()
            pulse_dict = response.json()

            # Extract malware family names from the nested structure
            families = [mf['display_name'] for mf in pulse_dict.get('malware_families', [])]
            pulse_dict['malware_families'] = families

            return ThreatPulse.model_validate(pulse_dict)
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to fetch details for pulse {pulse_id}: {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"An error occurred while fetching details for pulse {pulse_id}: {e}")
            return None

    async def search(
        self, 
        query: str, 
        limit: int = 5,  # Reduce default limit for faster summary searches
        fetch_full_details: bool = False
    ) -> ThreatFeedResponse:
        """
        Search for threat pulses on AlienVault OTX. 
        Can optionally fetch full details including IOCs for each pulse.
        
        Args:
            query: The search term (e.g., a malware family, threat actor, or campaign name).
            limit: The maximum number of results to return.
            fetch_full_details: If True, fetches full details for each pulse (slower).
            
        Returns:
            A ThreatFeedResponse object containing the search results.
        """
        params = {"q": query, "limit": min(limit, 20)} # Keep a reasonable max limit
        search_url = f"{self.base_url}/search/pulses"

        try:
            # Step 1: Always get the list of pulse summaries
            search_response = await self.client.get(search_url, params=params)
            search_response.raise_for_status()
            search_data = search_response.json()
            pulse_summaries = search_data.get("results", [])

            final_pulses: List[Union[ThreatPulse, ThreatPulseSummary]] = []
            # Step 2: If requested, concurrently fetch the full details
            if fetch_full_details:
                detail_tasks = [self.get_pulse_details(pulse['id']) for pulse in pulse_summaries]
                detailed_pulses_results = await asyncio.gather(*detail_tasks)
                # Filter out any pulses that failed to fetch
                final_pulses = [pulse for pulse in detailed_pulses_results if pulse is not None]
            else:
                # Otherwise, just parse the summary data we already have using the new model
                for summary in pulse_summaries:
                    final_pulses.append(ThreatPulseSummary.model_validate(summary))

            return ThreatFeedResponse(
                query=query,
                total_results=search_data.get("count", 0),
                results=final_pulses
            )
                
        except httpx.HTTPStatusError as e:
            error_message = f"OTX API search error: {e.response.status_code} - {e.response.text}"
            logger.error(error_message)
            return ThreatFeedResponse(
                status="error",
                query=query,
                total_results=0,
                results=[],
                error=error_message
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