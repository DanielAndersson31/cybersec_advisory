"""
Simple IOC analysis tool using VirusTotal API with Pydantic models.
"""

import asyncio
import logging
import re
from typing import List, Optional, Literal, Dict
import httpx
from pydantic import BaseModel, Field, ConfigDict
from config.settings import settings
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)


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
    description: str = "Analyze IOCs (single or batch). For batch analysis, provide indicators as comma-separated string."
    vt_api_key: str = Field(default_factory=lambda: settings.get_secret("virustotal_api_key"))
    base_url: str = "https://www.virustotal.com/api/v3"
    patterns: Dict[str, re.Pattern] = {}
    
    malicious_threshold: int = Field(default=3, description="Minimum detections to classify as malicious")
    suspicious_threshold: int = Field(default=3, description="Minimum detections to classify as suspicious")

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    def __init__(self, **data):
        super().__init__(**data)
        if not self.vt_api_key:
            raise ValueError("VIRUSTOTAL_API_KEY not configured in settings")
        
        self.patterns = {
            "ip": re.compile(r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$"),
            "domain": re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9-]{0,61}[a-zA-Z0-9]?\.[a-zA-Z]{2,}$"),
            "url": re.compile(r"^https?://"),
            "md5": re.compile(r"^[a-fA-F0-9]{32}$"),
            "sha1": re.compile(r"^[a-fA-F0-9]{40}$"),
            "sha256": re.compile(r"^[a-fA-F0-9]{64}$")
        }

    def _run(self, indicator: str) -> IOCAnalysisResponse:
        """Analyze indicator(s) using VirusTotal. Supports single indicator or comma-separated batch."""
        return asyncio.run(self._arun(indicator))

    async def _arun(self, indicator: str) -> IOCAnalysisResponse:
        """Analyze indicator(s) using VirusTotal. Supports single indicator or comma-separated batch."""
        if ',' in indicator:
            indicators = [ioc.strip() for ioc in indicator.split(',') if ioc.strip()]
            return await self.analyze_indicators(indicators)
        else:
            result = await self.analyze_indicator(indicator)
            return IOCAnalysisResponse(
                status="success",
                query=indicator,
                total_indicators=1,
                results=[result]
            )

    async def analyze_indicators(self, indicators: List[str]) -> IOCAnalysisResponse:
        """
        Analyze a list of indicators concurrently.
        
        Args:
            indicators: A list of indicators to analyze.
            
        Returns:
            An IOCAnalysisResponse object with the analysis findings for all indicators.
        """
        tasks = [self.analyze_indicator(indicator) for indicator in indicators]
        results = await asyncio.gather(*tasks)
        
        return IOCAnalysisResponse(
            total_indicators=len(indicators),
            results=results
        )

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
        
        # Determine classification using configurable thresholds
        if malicious >= self.malicious_threshold:
            classification = "malicious"
        elif suspicious >= self.suspicious_threshold or malicious > 0:
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