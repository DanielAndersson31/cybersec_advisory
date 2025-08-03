"""
Threat intelligence feeds from AlienVault OTX, CISA, and MISP.
"""

import os
import requests
from typing import List, Optional, Literal
from pydantic import BaseModel
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


# Pydantic Models
class ThreatIndicator(BaseModel):
    """Threat indicator from feeds"""
    indicator: str
    type: str
    threat_score: Optional[int] = None
    source: str
    last_seen: Optional[str] = None


class ThreatPulse(BaseModel):
    """AlienVault OTX Pulse"""
    id: str
    name: str
    description: str
    author: str
    created: str
    modified: str
    tags: List[str] = []
    indicators_count: int = 0
    adversary: Optional[str] = None
    malware_families: List[str] = []


class CISAAlert(BaseModel):
    """CISA security alert"""
    id: str
    title: str
    summary: str
    published: str
    severity: Optional[str] = None
    url: str


class MISPEvent(BaseModel):
    """MISP threat event"""
    id: str
    info: str
    date: str
    threat_level: str
    analysis_status: str
    tags: List[str] = []
    attribute_count: int = 0


class ThreatFeedResponse(BaseModel):
    """Combined response from all threat feeds"""
    status: str = "success"
    query: str
    otx_pulses: List[ThreatPulse] = []
    cisa_alerts: List[CISAAlert] = []
    misp_events: List[MISPEvent] = []
    indicators: List[ThreatIndicator] = []
    total_results: int = 0
    sources_checked: List[str] = []
    error: Optional[str] = None


class ThreatFeedsTool:
    """Fetch threat intelligence from multiple sources"""
    
    def __init__(self):
        """Initialize API connections"""
        # AlienVault OTX
        self.otx_api_key = os.getenv("OTX_API_KEY")
        self.otx_base_url = "https://otx.alienvault.com/api/v1"
        
        # MISP
        self.misp_url = os.getenv("MISP_URL", "")
        self.misp_api_key = os.getenv("MISP_API_KEY", "")
        
        # CISA doesn't require auth
        self.cisa_base_url = "https://www.cisa.gov/api/v1"
    
    async def search_feeds(
        self,
        query: str,
        feed_types: Optional[List[str]] = None,
        time_range: Optional[str] = None,
        confidence_threshold: float = 0.7
    ) -> ThreatFeedResponse:
        """
        Search threat intelligence feeds from OTX, CISA, and MISP.
        
        Args:
            query: Search query
            feed_types: Which feeds to search ['otx', 'cisa', 'misp']
            time_range: Time filter ('day', 'week', 'month')
            confidence_threshold: Not used currently
            
        Returns:
            Combined threat intelligence from all sources
        """
        sources_checked = []
        response = ThreatFeedResponse(query=query)
        
        # Default to all feeds if none specified
        if not feed_types:
            feed_types = ['otx', 'cisa', 'misp']
        
        try:
            # Search AlienVault OTX
            if 'otx' in feed_types and self.otx_api_key:
                otx_results = await self._search_otx(query, time_range)
                response.otx_pulses = otx_results["pulses"]
                response.indicators.extend(otx_results["indicators"])
                sources_checked.append("AlienVault OTX")
            
            # Search CISA alerts
            if 'cisa' in feed_types:
                cisa_results = await self._search_cisa(query, time_range)
                response.cisa_alerts = cisa_results
                sources_checked.append("CISA")
            
            # Search MISP
            if 'misp' in feed_types and self.misp_url and self.misp_api_key:
                misp_results = await self._search_misp(query, time_range)
                response.misp_events = misp_results["events"]
                response.indicators.extend(misp_results["indicators"])
                sources_checked.append("MISP")
            
            # Calculate total results
            response.total_results = (
                len(response.otx_pulses) + 
                len(response.cisa_alerts) + 
                len(response.misp_events)
            )
            response.sources_checked = sources_checked
            
            return response
            
        except Exception as e:
            logger.error(f"Threat feed search error: {str(e)}")
            response.status = "error"
            response.error = str(e)
            return response
    
    async def _search_otx(self, query: str, time_range: Optional[str]) -> dict:
        """Search AlienVault OTX pulses"""
        headers = {"X-OTX-API-KEY": self.otx_api_key}
        pulses = []
        indicators = []
        
        try:
            # Search pulses
            search_url = f"{self.otx_base_url}/search/pulses"
            params = {"q": query, "limit": 20}
            
            # Add time filter
            if time_range:
                days = {"day": 1, "week": 7, "month": 30}.get(time_range, 30)
                modified_since = (datetime.now() - timedelta(days=days)).isoformat()
                params["modified_since"] = modified_since
            
            response = requests.get(search_url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                
                for pulse in data.get("results", []):
                    # Create pulse object
                    pulse_obj = ThreatPulse(
                        id=pulse.get("id", ""),
                        name=pulse.get("name", ""),
                        description=pulse.get("description", "")[:200],
                        author=pulse.get("author_name", ""),
                        created=pulse.get("created", ""),
                        modified=pulse.get("modified", ""),
                        tags=pulse.get("tags", []),
                        indicators_count=pulse.get("indicator_count", 0),
                        adversary=pulse.get("adversary", ""),
                        malware_families=pulse.get("malware_families", [])
                    )
                    pulses.append(pulse_obj)
                    
                    # Get indicators from pulse (limited)
                    if pulse.get("indicator_count", 0) > 0:
                        pulse_id = pulse.get("id")
                        indicators_url = f"{self.otx_base_url}/pulses/{pulse_id}/indicators"
                        ind_response = requests.get(indicators_url, headers=headers, params={"limit": 5})
                        
                        if ind_response.status_code == 200:
                            ind_data = ind_response.json()
                            for ind in ind_data.get("results", [])[:5]:
                                indicators.append(ThreatIndicator(
                                    indicator=ind.get("indicator", ""),
                                    type=ind.get("type", ""),
                                    source="AlienVault OTX",
                                    last_seen=ind.get("created", "")
                                ))
            
        except Exception as e:
            logger.error(f"OTX search error: {str(e)}")
        
        return {"pulses": pulses, "indicators": indicators}
    
    async def _search_cisa(self, query: str, time_range: Optional[str]) -> List[CISAAlert]:
        """Search CISA alerts"""
        alerts = []
        
        try:
            # CISA provides alerts via their catalog API
            # Using known advisories endpoint
            url = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
            
            response = requests.get(url)
            
            if response.status_code == 200:
                data = response.json()
                vulnerabilities = data.get("vulnerabilities", [])
                
                # Filter by query
                for vuln in vulnerabilities[:20]:  # Limit results
                    if (query.lower() in vuln.get("product", "").lower() or
                        query.lower() in vuln.get("vulnerabilityName", "").lower() or
                        query.upper() in vuln.get("cveID", "")):
                        
                        alert = CISAAlert(
                            id=vuln.get("cveID", ""),
                            title=vuln.get("vulnerabilityName", ""),
                            summary=vuln.get("shortDescription", ""),
                            published=vuln.get("dateAdded", ""),
                            severity="high",  # CISA KEV are all high priority
                            url=f"https://nvd.nist.gov/vuln/detail/{vuln.get('cveID', '')}"
                        )
                        alerts.append(alert)
            
        except Exception as e:
            logger.error(f"CISA search error: {str(e)}")
        
        return alerts
    
    async def _search_misp(self, query: str, time_range: Optional[str]) -> dict:
        """Search MISP events"""
        headers = {
            "Authorization": self.misp_api_key,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        events = []
        indicators = []
        
        try:
            # Search events
            search_url = f"{self.misp_url}/events/restSearch"
            
            # Build search request
            search_data = {
                "returnFormat": "json",
                "searchall": query,
                "limit": 20
            }
            
            # Add time filter
            if time_range:
                days = {"day": 1, "week": 7, "month": 30}.get(time_range, 30)
                search_data["timestamp"] = f"{days}d"
            
            response = requests.post(search_url, headers=headers, json=search_data)
            
            if response.status_code == 200:
                data = response.json()
                
                for event in data.get("response", []):
                    event_data = event.get("Event", {})
                    
                    # Create event object
                    event_obj = MISPEvent(
                        id=event_data.get("id", ""),
                        info=event_data.get("info", ""),
                        date=event_data.get("date", ""),
                        threat_level=event_data.get("threat_level_id", ""),
                        analysis_status=event_data.get("analysis", ""),
                        tags=[tag.get("name", "") for tag in event_data.get("Tag", [])],
                        attribute_count=event_data.get("attribute_count", 0)
                    )
                    events.append(event_obj)
                    
                    # Extract some attributes as indicators
                    for attr in event_data.get("Attribute", [])[:5]:
                        if attr.get("type") in ["ip-dst", "domain", "url", "md5", "sha256"]:
                            indicators.append(ThreatIndicator(
                                indicator=attr.get("value", ""),
                                type=attr.get("type", ""),
                                source="MISP",
                                last_seen=attr.get("timestamp", "")
                            ))
            
        except Exception as e:
            logger.error(f"MISP search error: {str(e)}")
        
        return {"events": events, "indicators": indicators}


# Create singleton instance
threat_feeds_tool = ThreatFeedsTool()


# Export function
async def search_threat_feeds(**kwargs) -> dict:
    """Threat feeds function that MCP servers will import"""
    response = await threat_feeds_tool.search_feeds(**kwargs)
    return response.model_dump()