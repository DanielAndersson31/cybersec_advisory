"""
Simple IOC analysis tool using VirusTotal API with Pydantic models.
"""

import os
import re
import requests
from typing import List, Optional, Literal
from pydantic import BaseModel, Field
import logging

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


class IOCAnalysisTool:
    """Analyze IOCs using VirusTotal API"""
    
    def __init__(self):
        """Initialize with VirusTotal API key"""
        self.vt_api_key = os.getenv("VIRUSTOTAL_API_KEY")
        if not self.vt_api_key:
            logger.warning("VIRUSTOTAL_API_KEY not set - IOC analysis will be limited")
        
        self.vt_base_url = "https://www.virustotal.com/api/v3"
        
        # Simple patterns to identify IOC types
        self.patterns = {
            "ip": re.compile(r'^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$'),
            "domain": re.compile(r'^(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$'),
            "url": re.compile(r'^https?://'),
            "md5": re.compile(r'^[a-fA-F0-9]{32}$'),
            "sha1": re.compile(r'^[a-fA-F0-9]{40}$'),
            "sha256": re.compile(r'^[a-fA-F0-9]{64}$')
        }
    
    async def analyze(
        self,
        indicators: List[str],
        check_reputation: bool = True,
        enrich_data: bool = True,
        include_context: bool = True
    ) -> IOCAnalysisResponse:
        """
        Analyze indicators using VirusTotal.
        
        Args:
            indicators: List of IOCs to check
            check_reputation: Check against threat intelligence
            enrich_data: Not used (kept for compatibility)
            include_context: Not used (kept for compatibility)
            
        Returns:
            IOCAnalysisResponse with typed results
        """
        try:
            results = []
            
            for indicator in indicators:
                # Determine type
                indicator_type = self._determine_type(indicator)
                
                if indicator_type == "unknown":
                    results.append(IOCResult(
                        indicator=indicator,
                        type="unknown",
                        error="Could not determine indicator type"
                    ))
                    continue
                
                # Check with VirusTotal if API key available
                if check_reputation and self.vt_api_key:
                    result = await self._check_virustotal(indicator, indicator_type)
                else:
                    result = IOCResult(
                        indicator=indicator,
                        type=indicator_type,
                        classification="unknown",
                        error="No API key available"
                    )
                
                results.append(result)
            
            return IOCAnalysisResponse(
                total_indicators=len(indicators),
                results=results
            )
            
        except Exception as e:
            logger.error(f"IOC analysis error: {str(e)}")
            return IOCAnalysisResponse(
                status="error",
                total_indicators=len(indicators),
                results=[],
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
                url = f"{self.vt_base_url}/ip_addresses/{indicator}"
            elif indicator_type == "domain":
                url = f"{self.vt_base_url}/domains/{indicator}"
            elif indicator_type == "url":
                # URLs need to be base64 encoded
                import base64
                url_id = base64.urlsafe_b64encode(indicator.encode()).decode().strip("=")
                url = f"{self.vt_base_url}/urls/{url_id}"
            elif indicator_type in ["md5", "sha1", "sha256"]:
                url = f"{self.vt_base_url}/files/{indicator}"
            else:
                return IOCResult(
                    indicator=indicator,
                    type=indicator_type,
                    error="Unsupported type for VirusTotal"
                )
            
            # Make request
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                return self._parse_vt_response(indicator, indicator_type, data)
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


# Create singleton instance
ioc_analysis_tool = IOCAnalysisTool()


# Export function - returns dict for compatibility
async def analyze_indicators(**kwargs) -> dict:
    """IOC analysis function that MCP servers will import"""
    response = await ioc_analysis_tool.analyze(**kwargs)
    return response.model_dump()