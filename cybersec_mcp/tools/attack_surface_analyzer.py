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
    base_url: str = "https://api.zoomeye.ai"

    def __init__(self, **data):
        super().__init__(**data)
        if not self.api_key:
            raise ValueError("ZOOMEYE_API_KEY not configured in settings")

    def _run(self, host: str) -> Dict[str, Any]:
        """Analyzes a host (IP or domain) using the ZoomEye API."""
        return asyncio.run(self.analyze(host))

    async def _arun(self, host: str) -> Dict[str, Any]:
        """Analyzes a host (IP or domain) using the ZoomEye API."""
        result = await self.analyze(host)
        return result.model_dump()

    async def analyze(self, host: str) -> AttackSurfaceResponse:
        """
        Analyzes a host (IP or domain) using the ZoomEye API.
        
        Args:
            host: The IP address or domain name to analyze.
            
        Returns:
            An AttackSurfaceResponse with details of the host's exposure.
        """
        async with httpx.AsyncClient() as client:
            # Extract hostname from URL if needed
            hostname = self._extract_hostname(host)
            
            # ZoomEye's API uses GET requests with query parameters
            url = f"{self.base_url}/host/search"
            headers = {"API-KEY": self.api_key}
            
            # Build query parameters
            params = {
                "query": f'ip:"{hostname}"' if self._is_ip(hostname) else f'hostname:"{hostname}"',
                "page": 1
            }
            
            try:
                # Make the API request using GET
                api_response = await client.get(url, headers=headers, params=params)
                
                if api_response.status_code == 402:
                    data = api_response.json()
                    if data.get("code") == "credits_insufficent":
                        return AttackSurfaceResponse(
                            status="error",
                            query_host=host,
                            ip_address="",
                            error="ZoomEye API Error: Insufficient credits. Please check your ZoomEye account plan and usage."
                        )

                if api_response.status_code == 401:
                    return AttackSurfaceResponse(
                        status="error",
                        query_host=host,
                        ip_address="",
                        error="ZoomEye API Error: Unauthorized. Please check your API key."
                    )

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
                        ip_address=hostname if self._is_ip(hostname) else "",
                        status="success", # It's a success, just no data found
                        error="Host not found in ZoomEye database."
                    )

                # Process all matches to get comprehensive port information
                port_details = []
                main_match = matches[0]
                ip_address = main_match.get("ip", "")
                organization = main_match.get("organization", "N/A")
                country = main_match.get("geoinfo", {}).get("country", {}).get("name", "N/A")

                # Collect ports from all matches for this host
                for match in matches:
                    if match.get("portinfo"):
                        port_info = match["portinfo"]
                        port_details.append(OpenPortInfo(
                            port=port_info.get("port", 0),
                            service=port_info.get("service", "unknown"),
                            banner=(port_info.get("banner", "")[:200] + "...") if len(port_info.get("banner", "")) > 200 else port_info.get("banner", "")
                        ))

                return AttackSurfaceResponse(
                    query_host=host,
                    ip_address=ip_address,
                    organization=organization,
                    country=country,
                    open_ports=port_details
                )

            except httpx.HTTPError as e:
                logger.error(f"HTTP error during attack surface analysis: {str(e)}")
                return AttackSurfaceResponse(
                    status="error",
                    query_host=host,
                    ip_address="",
                    error=f"Network error: {str(e)}"
                )
            except Exception as e:
                logger.error(f"Attack surface analysis error: {str(e)}")
                return AttackSurfaceResponse(
                    status="error",
                    query_host=host,
                    ip_address="",
                    error=str(e)
                )

    def _extract_hostname(self, host: str) -> str:
        """Extract hostname from a full URL or return the host as-is."""
        if host.startswith(('http://', 'https://')):
            from urllib.parse import urlparse
            parsed = urlparse(host)
            return parsed.hostname or parsed.netloc
        return host

    def _is_ip(self, host: str) -> bool:
        """Check if the host is an IP address."""
        import re
        ipv4_pattern = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
        return bool(re.match(ipv4_pattern, host))