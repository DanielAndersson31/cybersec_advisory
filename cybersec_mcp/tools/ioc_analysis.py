"""
Simple IOC analysis tool using VirusTotal API with Pydantic models.
"""

import logging
import re
from typing import List, Optional, Literal, Dict
import httpx
from pydantic import BaseModel, Field, ConfigDict
from config.settings import settings
from langchain_core.tools import BaseTool
import asyncio

logger = logging.getLogger(__name__)


# Pydantic Models
class IOCType(BaseModel):
    """Supported IOC types"""
    type: Literal["ip", "domain", "url", "md5", "sha1", "sha256", "unknown"]


class IOCResult(BaseModel):
    """Individual IOC analysis result"""
    indicator: str
    type: str
    classification: Literal["malicious", "suspicious", "clean", "unknown"] = "unknown"
    malicious_count: int = 0
    total_engines: int = 0
    source: str = "virustotal"
    recommendation: Optional[str] = None
    error: Optional[str] = None


class IOCAnalysisResponse(BaseModel):
    """Response model for IOC analysis"""
    status: str = "success"
    total_indicators: int
    results: List[IOCResult]
    error: Optional[str] = None


class IOCAnalysisTool(BaseTool):
    """Tool for analyzing indicators of compromise using VirusTotal API"""
    name: str = "ioc_analysis"
    description: str = "Analyze an Indicator of Compromise (IOC) like IP address, domain, or file hash."
    vt_api_key: str = Field(default_factory=lambda: settings.get_secret("virustotal_api_key"))
    base_url: str = "https://www.virustotal.com/api/v3"
    patterns: Dict[str, re.Pattern] = {}

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    def __init__(self, **data):
        super().__init__(**data)
        if not self.vt_api_key:
            raise ValueError("VIRUSTOTAL_API_KEY not configured in settings")
        
        # Regex patterns for IOC type detection
        self.patterns = {
            "ip": re.compile(r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$"),
            "domain": re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9-]{0,61}[a-zA-Z0-9]?\.[a-zA-Z]{2,}$"),
            "url": re.compile(r"^https?://"),
            "md5": re.compile(r"^[a-fA-F0-9]{32}$"),
            "sha1": re.compile(r"^[a-fA-F0-9]{40}$"),
            "sha256": re.compile(r"^[a-fA-F0-9]{64}$")
        }

    def _run(self, indicator: str) -> IOCResult:
        """Analyze a single indicator using VirusTotal."""
        return asyncio.run(self.analyze_indicator(indicator))

    async def _arun(self, indicator: str) -> IOCResult:
        """Analyze a single indicator using VirusTotal."""
        return await self.analyze_indicator(indicator)

    async def analyze_indicator(self, indicator: str) -> IOCResult:
        """
        Analyze a single indicator using VirusTotal.
        
        Args:
            indicator: The indicator to analyze (IP, domain, URL, MD5, SHA1, SHA256)
            
        Returns:
            An IOCResult object with the analysis findings.
        """
        try:
            indicator_type = self._determine_type(indicator)
            
            if indicator_type == "unknown":
                return IOCResult(
                    indicator=indicator,
                    type="unknown",
                    error="Could not determine indicator type"
                )
            
            return await self._check_virustotal(indicator, indicator_type)
            
        except Exception as e:
            logger.error(f"IOC analysis error: {str(e)}")
            return IOCResult(
                indicator=indicator,
                type="unknown",
                error=str(e)
            )
    
    def _determine_type(self, indicator: str) -> str:
        """Determine what type of IOC this is"""
        indicator = indicator.strip()
        
        for ioc_type, pattern in self.patterns.items():
            if pattern.match(indicator):
                return ioc_type
        
        return "unknown"
    
    async def _check_virustotal(self, indicator: str, indicator_type: str) -> IOCResult:
        """Check indicator with VirusTotal API"""
        headers = {"x-apikey": self.vt_api_key}
        
        try:
            # Build URL based on type
            if indicator_type == "ip":
                url = f"{self.base_url}/ip_addresses/{indicator}"
            elif indicator_type == "domain":
                url = f"{self.base_url}/domains/{indicator}"
            elif indicator_type == "url":
                # URLs need to be base64 encoded
                import base64
                url_id = base64.urlsafe_b64encode(indicator.encode()).decode().strip("=")
                url = f"{self.base_url}/urls/{url_id}"
            elif indicator_type in ["md5", "sha1", "sha256"]:
                url = f"{self.base_url}/files/{indicator}"
            else:
                return IOCResult(
                    indicator=indicator,
                    type=indicator_type,
                    classification="unknown",
                    error="Unsupported type for VirusTotal"
                )
            
            async with httpx.AsyncClient() as client:
                # Make request
                response = await client.get(url, headers=headers)
            
            if response.status_code == 200:
                return self._parse_vt_response(indicator, indicator_type, response.json())
            elif response.status_code == 404:
                return IOCResult(
                    indicator=indicator,
                    type=indicator_type,
                    classification="unknown",
                    error="Not found in VirusTotal"
                )
            else:
                return IOCResult(
                    indicator=indicator,
                    type=indicator_type,
                    error=f"VirusTotal API error: {response.status_code}"
                )
                
        except Exception as e:
            return IOCResult(
                indicator=indicator,
                type=indicator_type,
                error=str(e)
            )
    
    def _parse_vt_response(self, indicator: str, indicator_type: str, data: dict) -> IOCResult:
        """Parse VirusTotal response into IOCResult"""
        attributes = data.get("data", {}).get("attributes", {})
        stats = attributes.get("last_analysis_stats", {})
        
        malicious = stats.get("malicious", 0)
        suspicious = stats.get("suspicious", 0)
        total = sum(stats.values())
        
        # Determine classification
        if malicious > 3:
            classification = "malicious"
        elif suspicious > 3 or malicious > 0:
            classification = "suspicious"
        else:
            classification = "clean"
        
        # Build recommendation
        recommendation = None
        if classification == "malicious":
            recommendation = f"Block this {indicator_type} - detected by {malicious} engines"
        elif classification == "suspicious":
            recommendation = f"Monitor this {indicator_type} - flagged by {suspicious + malicious} engines"
        
        return IOCResult(
            indicator=indicator,
            type=indicator_type,
            classification=classification,
            malicious_count=malicious,
            total_engines=total,
            recommendation=recommendation
        )