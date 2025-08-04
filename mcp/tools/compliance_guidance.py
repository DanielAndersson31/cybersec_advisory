"""
Simple compliance guidance tool for cybersecurity incidents.
"""

import sys
import os
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import logging

# Add parent directory to path to import config
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

try:
    from config.compliance_frameworks import (
        ComplianceFramework,
        get_applicable_frameworks,
        get_strictest_breach_timeline,
        get_framework_summary,
        get_breach_timeline
    )
except ImportError:
    # Fallback if import fails
    logging.warning("Could not import compliance frameworks config")
    ComplianceFramework = None

logger = logging.getLogger(__name__)


# Pydantic Models
class ComplianceRecommendation(BaseModel):
    """Individual compliance recommendation"""
    framework: str
    framework_name: str
    applies: bool
    breach_notification_hours: Optional[int] = None
    key_requirements: List[str] = []
    max_penalty: str = "Unknown"
    next_actions: List[str] = []


class ComplianceGuidanceResponse(BaseModel):
    """Response model for compliance guidance"""
    status: str = "success"
    query_context: str
    applicable_frameworks: List[ComplianceRecommendation] = []
    immediate_actions: List[str] = []
    strictest_timeline_hours: Optional[int] = None
    error: Optional[str] = None


class ComplianceGuidanceTool:
    """Provide compliance guidance for cybersecurity incidents"""
    
    def __init__(self):
        """Initialize compliance guidance tool"""
        if not ComplianceFramework:
            logger.warning("Compliance frameworks not available - guidance will be limited")
    
    async def get_guidance(
        self,
        incident_type: str = "data_breach",
        data_types: Optional[List[str]] = None,
        regions: Optional[List[str]] = None,
        organization_type: Optional[str] = None
    ) -> ComplianceGuidanceResponse:
        """
        Get compliance guidance for a cybersecurity incident.
        
        Args:
            incident_type: Type of incident (data_breach, ransomware, phishing, etc.)
            data_types: Types of data involved (personal_data, health_data, payment_cards, financial_records)
            regions: Geographic regions (EU, US, Global)
            organization_type: Type of organization (healthcare, financial, public, private)
            
        Returns:
            ComplianceGuidanceResponse with applicable frameworks and timelines
        """
        try:
            if not ComplianceFramework:
                return ComplianceGuidanceResponse(
                    status="error",
                    query_context=f"{incident_type} incident",
                    error="Compliance frameworks configuration not available"
                )
            
            query_context = f"{incident_type} incident"
            if data_types:
                query_context += f" involving {', '.join(data_types)}"
            if regions:
                query_context += f" in {', '.join(regions)}"
            
            # Determine applicable frameworks
            applicable_frameworks = []
            all_frameworks = set()
            
            # Check by data type
            if data_types:
                for data_type in data_types:
                    frameworks = get_applicable_frameworks(data_type=data_type)
                    all_frameworks.update(frameworks)
            
            # Check by region
            if regions:
                for region in regions:
                    frameworks = get_applicable_frameworks(region=region)
                    all_frameworks.update(frameworks)
            
            # If no specific criteria, check common frameworks
            if not all_frameworks:
                all_frameworks = {ComplianceFramework.GDPR, ComplianceFramework.HIPAA, 
                                ComplianceFramework.PCI_DSS, ComplianceFramework.SOX}
            
            # Build recommendations for each framework
            for framework in all_frameworks:
                recommendation = self._build_recommendation(
                    framework, incident_type, data_types, regions, organization_type
                )
                applicable_frameworks.append(recommendation)
            
            # Sort by applicability (most relevant first)
            applicable_frameworks.sort(key=lambda x: x.applies, reverse=True)
            
            # Get strictest timeline
            applying_frameworks = [fw for fw in all_frameworks 
                                 if self._framework_applies(fw, data_types, regions, organization_type)]
            strictest_timeline = get_strictest_breach_timeline(applying_frameworks)
            strictest_hours = None
            if strictest_timeline:
                strictest_hours = int(strictest_timeline.total_seconds() / 3600)
            
            # Generate immediate actions
            immediate_actions = self._get_immediate_actions(
                incident_type, applying_frameworks, strictest_hours
            )
            
            return ComplianceGuidanceResponse(
                query_context=query_context,
                applicable_frameworks=applicable_frameworks,
                immediate_actions=immediate_actions,
                strictest_timeline_hours=strictest_hours
            )
            
        except Exception as e:
            logger.error(f"Compliance guidance error: {str(e)}")
            return ComplianceGuidanceResponse(
                status="error",
                query_context=f"{incident_type} incident",
                error=str(e)
            )
    
    def _build_recommendation(
        self,
        framework,
        incident_type: str,
        data_types: Optional[List[str]],
        regions: Optional[List[str]],
        organization_type: Optional[str]
    ) -> ComplianceRecommendation:
        """Build compliance recommendation for a framework"""
        summary = get_framework_summary(framework)
        applies = self._framework_applies(framework, data_types, regions, organization_type)
        
        # Get breach notification timeline
        timeline = get_breach_timeline(framework, "authority")
        timeline_hours = None
        if timeline:
            timeline_hours = int(timeline.total_seconds() / 3600)
        
        # Generate next actions
        next_actions = []
        if applies and incident_type == "data_breach":
            if timeline_hours:
                if timeline_hours <= 24:
                    next_actions.append(f"URGENT: Notify authorities within {timeline_hours} hours")
                else:
                    next_actions.append(f"Notify authorities within {timeline_hours // 24} days")
            
            next_actions.extend([
                "Document the incident details",
                "Assess scope of data involved",
                "Prepare breach notification documentation"
            ])
        elif applies:
            next_actions.extend([
                "Review framework requirements",
                "Document security controls",
                "Assess compliance impact"
            ])
        
        return ComplianceRecommendation(
            framework=framework.value,
            framework_name=summary.get("name", framework.value.upper()),
            applies=applies,
            breach_notification_hours=timeline_hours,
            key_requirements=summary.get("key_points", [])[:3],  # Top 3 requirements
            max_penalty=summary.get("max_penalty", "Unknown"),
            next_actions=next_actions
        )
    
    def _framework_applies(
        self,
        framework,
        data_types: Optional[List[str]],
        regions: Optional[List[str]],
        organization_type: Optional[str]
    ) -> bool:
        """Determine if a framework applies to the situation"""
        # Simple applicability logic
        framework_mapping = {
            ComplianceFramework.GDPR: {
                "data_types": ["personal_data"],
                "regions": ["EU"],
                "org_types": ["any"]
            },
            ComplianceFramework.HIPAA: {
                "data_types": ["health_data"],
                "regions": ["US"],
                "org_types": ["healthcare"]
            },
            ComplianceFramework.PCI_DSS: {
                "data_types": ["payment_cards"],
                "regions": ["any"],
                "org_types": ["any"]
            },
            ComplianceFramework.SOX: {
                "data_types": ["financial_records"],
                "regions": ["US"],
                "org_types": ["public"]
            }
        }
        
        mapping = framework_mapping.get(framework, {})
        
        # Check data types
        if data_types and mapping.get("data_types") != ["any"]:
            if not any(dt in mapping.get("data_types", []) for dt in data_types):
                return False
        
        # Check regions
        if regions and mapping.get("regions") != ["any"]:
            if not any(region in mapping.get("regions", []) for region in regions):
                return False
        
        # Check organization type
        if organization_type and mapping.get("org_types") != ["any"]:
            if organization_type not in mapping.get("org_types", []):
                return False
        
        return True
    
    def _get_immediate_actions(
        self,
        incident_type: str,
        frameworks,
        strictest_hours: Optional[int]
    ) -> List[str]:
        """Generate immediate action items"""
        actions = []
        
        # Time-critical actions first
        if strictest_hours:
            if strictest_hours <= 24:
                actions.append(f"⚠️  URGENT: You have {strictest_hours} hours for regulatory notification")
            else:
                actions.append(f"📅 You have {strictest_hours // 24} days for regulatory notification")
        
        # Common incident response actions
        if incident_type == "data_breach":
            actions.extend([
                "🔒 Contain the breach and secure affected systems",
                "📝 Document all incident details and timeline",
                "🔍 Assess what data was accessed/exfiltrated",
                "📞 Consider legal counsel for regulatory guidance"
            ])
        elif incident_type == "ransomware":
            actions.extend([
                "🚫 Do not pay ransom without legal consultation",
                "💾 Preserve forensic evidence",
                "📋 Check if personal data was accessed (triggers breach rules)"
            ])
        else:
            actions.extend([
                "📝 Document the incident",
                "🔍 Assess potential compliance impact",
                "📞 Consider regulatory consultation if unsure"
            ])
        
        return actions


# Create singleton instance
compliance_guidance_tool = ComplianceGuidanceTool()


# Export function for MCP server integration
async def get_compliance_guidance(**kwargs) -> dict:
    """Compliance guidance function that MCP servers will import"""
    response = await compliance_guidance_tool.get_guidance(**kwargs)
    return response.model_dump()
