"""
Simple attack surface analysis tool using the ZoomEye API.
"""

import httpx
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
import logging
from config.settings import settings
import asyncio

logger = logging.getLogger(__name__)


# Pydantic Models
class OpenPortInfo(BaseModel):
    """Details of a single open port found on a host."""
    port: int
    service: str
    banner: Optional[str] = None

class AttackSurfaceResponse(BaseModel):
    """Response model for the attack surface analysis."""
    status: str = "success"
    query_host: str
    ip_address: str
    organization: Optional[str] = None
    country: Optional[str] = None
    open_ports: List[OpenPortInfo] = []
    error: Optional[str] = None


class AttackSurfaceAnalyzerTool(BaseTool):
    """Tool for analyzing attack surface using ZoomEye API"""
    name: str = "attack_surface_analyzer"
    description: str = "Analyzes the attack surface of a domain or IP address."
    api_key: str = Field(default_factory=lambda: settings.get_secret("zoomeye_api_key"))
    base_url: str = "https://api.zoomeye.org"

    def __init__(self, **data):
        super().__init__(**data)
        if not self.api_key:
            raise ValueError("ZOOMEYE_API_KEY not configured in settings")

    def _run(self, host: str) -> Dict[str, Any]:
        """Analyzes a host (IP or domain) using the ZoomEye API."""
        return asyncio.run(self.analyze(host))

    async def _arun(self, host: str) -> Dict[str, Any]:
        """Analyzes a host (IP or domain) using the ZoomEye API."""
        return await self.analyze(host)

    async def analyze(self, host: str) -> Dict[str, Any]:
        """
        Analyzes a host (IP or domain) using the ZoomEye API.
        
        Args:
            host: The IP address or domain name to analyze.
            
        Returns:
            An AttackSurfaceResponse with details of the host's exposure.
        """
        async with httpx.AsyncClient() as client:
            # ZoomEye's primary search endpoint for hosts
            url = f"{self.base_url}/host/search"
            headers = {"API-KEY": self.api_key}
            # ZoomEye uses a query string format
            params = {"query": f'ip:"{host}" or hostname:"{host}"', "page": 1}
            
            try:
                # Make the API request
                api_response = await client.get(url, headers=headers, params=params)
                
                if api_response.status_code != 200:
                    return AttackSurfaceResponse(
                        status="error",
                        query_host=host,
                        ip_address="",
                        error=f"ZoomEye API error: {api_response.status_code} - {api_response.text}"
                    )
                
                # Parse the successful response
                data = api_response.json()
                matches = data.get("matches", [])
                
                if not matches:
                    return AttackSurfaceResponse(
                        query_host=host,
                        ip_address=host, # Assume host is IP if no results
                        status="success", # It's a success, just no data found
                        error="Host not found in ZoomEye database."
                    )

                # We'll use the first match as the primary source of info
                main_match = matches[0]
                port_details = []
                if main_match.get("portinfo"):
                    port_details.append(OpenPortInfo(
                        port=main_match["portinfo"].get("port"),
                        service=main_match["portinfo"].get("service"),
                        banner=main_match["portinfo"].get("banner", "")[:200] + "..." # Truncate long banners
                    ))

                return AttackSurfaceResponse(
                    query_host=host,
                    ip_address=main_match.get("ip", ""),
                    organization=main_match.get("organization", "N/A"),
                    country=main_match.get("geoinfo", {}).get("country", {}).get("name", "N/A"),
                    open_ports=port_details
                )

            except Exception as e:
                logger.error(f"Attack surface analysis error: {str(e)}")
                return AttackSurfaceResponse(
                    status="error",
                    query_host=host,
                    ip_address="",
                    error=str(e)
                )
