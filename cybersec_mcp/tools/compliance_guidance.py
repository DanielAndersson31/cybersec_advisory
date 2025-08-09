"""
Compliance guidance tool with all business logic.
Uses configuration data from compliance_frameworks.
"""

from typing import List, Optional, Dict
from pydantic import BaseModel
from datetime import timedelta
import logging

# Import configuration data only
from config.compliance_frameworks import (
    ComplianceFramework,
    BREACH_TIMELINES,
    FRAMEWORK_REQUIREMENTS,
    APPLICABILITY
)

logger = logging.getLogger(__name__)


# Pydantic Models
class BreachTimeline(BaseModel):
    """Breach notification timeline information"""
    authority_notification: Optional[str] = None
    individual_notification: Optional[str] = None
    threshold: str
    strictest_deadline: Optional[str] = None


class FrameworkGuidance(BaseModel):
    """Guidance for a specific framework"""
    framework: str
    full_name: str
    region: str
    applies_to: str
    key_requirements: List[str]
    max_penalty: str
    breach_timeline: BreachTimeline


class ComplianceRecommendation(BaseModel):
    """Compliance recommendations based on context"""
    applicable_frameworks: List[str]
    primary_framework: Optional[str] = None
    strictest_breach_deadline: Optional[str] = None
    immediate_actions: List[str] = []
    key_considerations: List[str] = []


class ComplianceGuidanceResponse(BaseModel):
    """Response model for compliance guidance"""
    status: str = "success"
    query: str
    framework_guidance: Optional[FrameworkGuidance] = None
    recommendations: Optional[ComplianceRecommendation] = None
    all_applicable: List[str] = []
    error: Optional[str] = None


class ComplianceGuidanceTool:
    """Provide compliance guidance with all business logic"""
    
    def __init__(self):
        """Initialize compliance guidance tool"""
        self.frameworks = list(ComplianceFramework)
    
    # === Private Helper Methods ===
    
    def _get_breach_timeline(self, framework: ComplianceFramework, target: str = "authority") -> Optional[timedelta]:
        """Get breach notification timeline"""
        timelines = BREACH_TIMELINES.get(framework, {})
        return timelines.get(target)
    
    def _get_applicable_frameworks(self, data_type: Optional[str] = None, region: Optional[str] = None) -> List[ComplianceFramework]:
        """Get frameworks that might apply"""
        frameworks = set()
        
        if data_type and data_type in APPLICABILITY["by_data_type"]:
            frameworks.update(APPLICABILITY["by_data_type"][data_type])
        
        if region and region in APPLICABILITY["by_region"]:
            frameworks.update(APPLICABILITY["by_region"][region])
        
        return list(frameworks)
    
    def _get_strictest_breach_timeline(self, frameworks: List[ComplianceFramework]) -> Optional[timedelta]:
        """Get the shortest breach notification timeline"""
        timelines = []
        for fw in frameworks:
            timeline = self._get_breach_timeline(fw, "authority")
            if timeline:
                timelines.append(timeline)
        
        return min(timelines) if timelines else None
    
    def _get_framework_summary(self, framework: ComplianceFramework) -> Dict:
        """Get summary information about a framework"""
        return FRAMEWORK_REQUIREMENTS.get(framework, {})
    
    # === Main Tool Methods ===
    
    def get_guidance(
        self,
        framework: Optional[str] = None,
        data_type: Optional[str] = None,
        region: Optional[str] = None,
        incident_type: Optional[str] = None
    ) -> ComplianceGuidanceResponse:
        """
        Get compliance guidance for specific framework or situation.
        
        Args:
            framework: Specific framework (GDPR, HIPAA, PCI-DSS, SOX)
            data_type: Type of data (personal_data, health_data, payment_cards, financial_records)
            region: Geographic region (EU, US, Global)
            incident_type: Type of incident (breach, vulnerability, etc.)
            
        Returns:
            ComplianceGuidanceResponse with guidance and recommendations
        """
        try:
            # If specific framework requested
            if framework:
                return self._get_framework_guidance(framework)
            
            # If data type or region provided, find applicable frameworks
            if data_type or region:
                return self._get_recommendations(data_type, region, incident_type)
            
            # Return general compliance overview
            return self._get_overview()
            
        except Exception as e:
            logger.error(f"Compliance guidance error: {str(e)}")
            return ComplianceGuidanceResponse(
                status="error",
                query=f"framework={framework}, data_type={data_type}, region={region}",
                error=str(e)
            )
    
    def _get_framework_guidance(self, framework_name: str) -> ComplianceGuidanceResponse:
        """Get detailed guidance for a specific framework"""
        try:
            # Convert string to enum
            fw_enum = ComplianceFramework(framework_name.lower())
            
            # Get framework details
            fw_info = self._get_framework_summary(fw_enum)
            if not fw_info:
                return ComplianceGuidanceResponse(
                    status="error",
                    query=framework_name,
                    error=f"Framework {framework_name} not found"
                )
            
            # Get breach timelines
            breach_timeline = self._format_breach_timeline(fw_enum)
            
            # Create guidance
            guidance = FrameworkGuidance(
                framework=fw_enum.value.upper(),
                full_name=fw_info["name"],
                region=fw_info["region"],
                applies_to=fw_info["applies_to"],
                key_requirements=fw_info["key_points"],
                max_penalty=fw_info["max_penalty"],
                breach_timeline=breach_timeline
            )
            
            return ComplianceGuidanceResponse(
                query=framework_name,
                framework_guidance=guidance,
                all_applicable=[fw_enum.value.upper()]
            )
            
        except ValueError:
            return ComplianceGuidanceResponse(
                status="error",
                query=framework_name,
                error=f"Unknown framework: {framework_name}"
            )
    
    def _get_recommendations(
        self, 
        data_type: Optional[str], 
        region: Optional[str],
        incident_type: Optional[str]
    ) -> ComplianceGuidanceResponse:
        """Get recommendations based on data type and region"""
        # Find applicable frameworks
        applicable = self._get_applicable_frameworks(data_type, region)
        
        if not applicable:
            return ComplianceGuidanceResponse(
                query=f"data_type={data_type}, region={region}",
                recommendations=ComplianceRecommendation(
                    applicable_frameworks=[],
                    key_considerations=["No specific frameworks identified for this scenario"]
                )
            )
        
        # Get strictest timeline if dealing with breach
        strictest_timeline = None
        if incident_type == "breach":
            timeline = self._get_strictest_breach_timeline(applicable)
            if timeline:
                strictest_timeline = self._format_timedelta(timeline)
        
        # Determine primary framework (most restrictive)
        primary = applicable[0] if applicable else None
        
        # Build recommendations
        recommendations = ComplianceRecommendation(
            applicable_frameworks=[fw.value.upper() for fw in applicable],
            primary_framework=primary.value.upper() if primary else None,
            strictest_breach_deadline=strictest_timeline
        )
        
        # Add immediate actions for breach
        if incident_type == "breach":
            recommendations.immediate_actions = [
                "Document the incident discovery time",
                "Assess the scope and impact",
                "Preserve evidence",
                f"Prepare notifications (deadline: {strictest_timeline or 'check frameworks'})",
                "Identify affected individuals/data"
            ]
        
        # Add key considerations
        for fw in applicable:
            fw_info = self._get_framework_summary(fw)
            if fw_info:
                recommendations.key_considerations.extend(fw_info["key_points"][:2])
        
        return ComplianceGuidanceResponse(
            query=f"data_type={data_type}, region={region}",
            recommendations=recommendations,
            all_applicable=[fw.value.upper() for fw in applicable]
        )
    
    def _get_overview(self) -> ComplianceGuidanceResponse:
        """Get general compliance overview"""
        all_frameworks = [fw.value.upper() for fw in ComplianceFramework]
        
        recommendations = ComplianceRecommendation(
            applicable_frameworks=all_frameworks,
            key_considerations=[
                "Identify what type of data you process",
                "Determine your geographic scope",
                "Assess which regulations apply",
                "Implement appropriate controls",
                "Maintain compliance documentation"
            ]
        )
        
        return ComplianceGuidanceResponse(
            query="overview",
            recommendations=recommendations,
            all_applicable=all_frameworks
        )
    
    def _format_breach_timeline(self, framework: ComplianceFramework) -> BreachTimeline:
        """Format breach timeline information"""
        timelines = BREACH_TIMELINES.get(framework, {})
        
        authority = timelines.get("authority")
        individuals = timelines.get("individuals")
        
        breach_timeline = BreachTimeline(
            authority_notification=self._format_timedelta(authority) if authority else None,
            individual_notification=self._format_timedelta(individuals) if individuals else None,
            threshold=timelines.get("threshold", "Unknown")
        )
        
        # Add strictest deadline
        if authority:
            breach_timeline.strictest_deadline = self._format_timedelta(authority)
        
        return breach_timeline
    
    def _format_timedelta(self, td: timedelta) -> str:
        """Convert timedelta to readable string"""
        total_seconds = int(td.total_seconds())
        
        if total_seconds < 3600:  # Less than an hour
            return f"{total_seconds // 60} minutes"
        elif total_seconds < 86400:  # Less than a day
            return f"{total_seconds // 3600} hours"
        else:
            return f"{total_seconds // 86400} days"


# Create singleton instance
compliance_guidance_tool = ComplianceGuidanceTool()


# Export function for compatibility
def get_compliance_guidance(**kwargs) -> dict:
    """Compliance guidance function that MCP servers will import"""
    response = compliance_guidance_tool.get_guidance(**kwargs)
    return response.model_dump()