"""
Centralized Pydantic schemas for all cybersecurity tools.
Organized by functional domain for easy maintenance and reuse.
"""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


# =============================================================================
# COMMON/SHARED SCHEMAS
# =============================================================================

class BaseToolResponse(BaseModel):
    """Base response schema for all cybersecurity tools"""
    status: str = Field(default="success", description="Status of the operation")
    query: str = Field(description="Original query that was processed")
    error: Optional[str] = Field(default=None, description="Error message if operation failed")


# =============================================================================
# WEB SEARCH SCHEMAS
# =============================================================================

class WebSearchResult(BaseModel):
    """A single web search result."""
    title: str = Field(description="Title of the search result")
    url: str = Field(description="URL of the search result")
    content: str = Field(description="Content snippet from the search result")
    score: float = Field(ge=0.0, description="Relevance score")
    published_date: Optional[str] = Field(description="Publication date if available")


class WebSearchResponse(BaseToolResponse):
    """The structured response for a web search query."""
    enhanced_query: str = Field(description="Enhanced or modified query used for search")
    results: List[WebSearchResult] = Field(description="List of search results")
    total_results: int = Field(ge=0, description="Total number of results returned")
    time_filter_applied: Optional[str] = Field(default=None, description="Time filter that was applied")


# =============================================================================
# KNOWLEDGE SEARCH SCHEMAS
# =============================================================================

class KnowledgeResult(BaseModel):
    """A single result from a knowledge base search."""
    doc_id: str
    content: str
    metadata: Dict[str, Any]
    score: float


class KnowledgeSearchResponse(BaseToolResponse):
    """The structured response for a knowledge search query."""
    domain_searched: Optional[str] = None
    results: List[KnowledgeResult]


# =============================================================================
# IOC ANALYSIS SCHEMAS
# =============================================================================

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


class IOCAnalysisResponse(BaseToolResponse):
    """Response model for IOC analysis"""
    total_indicators: int
    results: List[IOCResult]


# =============================================================================
# EXPOSURE CHECKER SCHEMAS
# =============================================================================

class ExposureDetails(BaseModel):
    """Details of a single exposure - simplified to match XposedOrNot API."""
    breach_name: str
    # Note: XposedOrNot api_v2 only provides breach names, not detailed metadata


class ExposureCheckResponse(BaseToolResponse):
    """The structured response for an exposure check."""
    is_exposed: bool
    exposure_count: int
    exposures: List[ExposureDetails] = []
    breach_names: Optional[List[str]] = None  # Raw breach names from API
    message: Optional[str] = None


# =============================================================================
# ATTACK SURFACE ANALYZER SCHEMAS
# =============================================================================

class OpenPortInfo(BaseModel):
    """Details of a single open port found on a host."""
    port: int
    service: str
    version: Optional[str] = None
    banner: Optional[str] = None


class AttackSurfaceResponse(BaseToolResponse):
    """Response model for the attack surface analysis."""
    query_host: str
    ip_address: str
    organization: Optional[str] = None
    country: Optional[str] = None
    open_ports: List[OpenPortInfo] = []


# =============================================================================
# VULNERABILITY SEARCH SCHEMAS
# =============================================================================

class CVEResult(BaseModel):
    """Individual CVE result"""
    cve_id: str
    description: str
    severity: str = "UNKNOWN"
    cvss_score: float = 0.0
    published_date: str


class VulnerabilitySearchResponse(BaseToolResponse):
    """Response model for vulnerability search"""
    total_results: int
    results: List[CVEResult]


# =============================================================================
# COMPLIANCE GUIDANCE SCHEMAS
# =============================================================================

class BreachTimeline(BaseModel):
    """Breach notification timeline information"""
    authority_notification: Optional[str] = None
    individual_notification: Optional[str] = None
    threshold: Optional[str] = None
    strictest_deadline: Optional[str] = None


class FrameworkGuidance(BaseModel):
    """Guidance for a specific framework"""
    framework: str
    full_name: str
    region: str
    applies_to: str
    key_points: List[str]
    max_penalty: str
    breach_timeline: BreachTimeline


class ComplianceRecommendation(BaseModel):
    """Compliance recommendations based on context"""
    applicable_frameworks: List[str]
    primary_framework: Optional[str] = None
    strictest_breach_deadline: Optional[str] = None
    immediate_actions: List[str] = []
    key_considerations: List[str] = []


class ComplianceGuidanceResponse(BaseToolResponse):
    """Response model for compliance guidance"""
    guidance: Optional[FrameworkGuidance] = None
    recommendations: Optional[ComplianceRecommendation] = None
    all_applicable: List[str] = []


# =============================================================================
# THREAT FEEDS SCHEMAS
# =============================================================================

class Indicator(BaseModel):
    """Represents a single Indicator of Compromise (IOC) from a Pulse."""
    indicator: str
    type: str
    description: Optional[str] = None


class ThreatPulseSummary(BaseModel):
    """Represents the summary of a threat pulse, returned from a search."""
    id: str
    name: str
    description: str
    author_name: str
    created: str
    modified: str
    tlp: str
    is_public: bool
    is_active: bool
    tags: List[str]
    targeted_countries: List[str]
    malware_families: List[str]
    attack_ids: List[str]
    industries: List[str]
    indicators: List[Indicator]


class ThreatFeedResponse(BaseToolResponse):
    """The structured response model for a threat feed search."""
    pulses: List[ThreatPulseSummary]
    total_count: int
