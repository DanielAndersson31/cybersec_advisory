"""
Simplified compliance frameworks configuration.
Essential regulatory information for cybersecurity compliance.
"""

from typing import Dict, List, Optional
from enum import Enum
from datetime import timedelta


class ComplianceFramework(Enum):
    """Supported compliance frameworks"""
    GDPR = "gdpr"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"
    SOX = "sox"
    ISO_27001 = "iso_27001"
    NIST = "nist"


# Breach notification timelines (most critical compliance info)
BREACH_TIMELINES = {
    ComplianceFramework.GDPR: {
        "authority": timedelta(hours=72),
        "individuals": timedelta(days=30),
        "threshold": "high risk to individuals"
    },
    ComplianceFramework.HIPAA: {
        "authority": timedelta(days=60),
        "individuals": timedelta(days=60),
        "threshold": "unsecured PHI"
    },
    ComplianceFramework.PCI_DSS: {
        "authority": timedelta(hours=24),  # To card brands
        "individuals": None,  # Determined by card brands
        "threshold": "any cardholder data compromise"
    },
    ComplianceFramework.SOX: {
        "authority": timedelta(days=4),  # Material events
        "individuals": None,
        "threshold": "material financial impact"
    }
}


# Key requirements summary (what agents need to know)
FRAMEWORK_REQUIREMENTS = {
    ComplianceFramework.GDPR: {
        "name": "General Data Protection Regulation",
        "region": "EU/EEA/UK",
        "applies_to": "personal data",
        "key_points": [
            "72-hour breach notification",
            "Right to erasure",
            "Data portability",
            "Privacy by design",
            "DPO required for some organizations"
        ],
        "max_penalty": "€20M or 4% global turnover"
    },
    ComplianceFramework.HIPAA: {
        "name": "Health Insurance Portability and Accountability Act",
        "region": "United States",
        "applies_to": "health information (PHI)",
        "key_points": [
            "Administrative, Physical, Technical safeguards",
            "Business Associate Agreements required",
            "Minimum necessary standard",
            "60-day breach notification",
            "Annual risk assessments"
        ],
        "max_penalty": "$2M per violation type/year"
    },
    ComplianceFramework.PCI_DSS: {
        "name": "Payment Card Industry Data Security Standard",
        "region": "Global",
        "applies_to": "payment card data",
        "key_points": [
            "12 core requirements",
            "Quarterly vulnerability scans",
            "Annual penetration testing",
            "Network segmentation",
            "Encryption of cardholder data"
        ],
        "max_penalty": "Loss of card processing ability"
    },
    ComplianceFramework.SOX: {
        "name": "Sarbanes-Oxley Act",
        "region": "United States",
        "applies_to": "public company financial data",
        "key_points": [
            "IT General Controls (ITGC)",
            "Internal controls testing",
            "Management certification",
            "Audit trails required",
            "Change management controls"
        ],
        "max_penalty": "$5M and 20 years imprisonment"
    }
}


# Simple applicability check
APPLICABILITY = {
    "by_data_type": {
        "personal_data": [ComplianceFramework.GDPR],
        "health_data": [ComplianceFramework.HIPAA],
        "payment_cards": [ComplianceFramework.PCI_DSS],
        "financial_records": [ComplianceFramework.SOX]
    },
    "by_region": {
        "EU": [ComplianceFramework.GDPR],
        "US": [ComplianceFramework.HIPAA, ComplianceFramework.SOX],
        "Global": [ComplianceFramework.PCI_DSS, ComplianceFramework.ISO_27001]
    }
}


# Helper functions
def get_breach_timeline(framework: ComplianceFramework, target: str = "authority") -> Optional[timedelta]:
    """Get breach notification timeline"""
    timelines = BREACH_TIMELINES.get(framework, {})
    return timelines.get(target)


def get_applicable_frameworks(data_type: Optional[str] = None, region: Optional[str] = None) -> List[ComplianceFramework]:
    """Get frameworks that might apply"""
    frameworks = set()
    
    if data_type and data_type in APPLICABILITY["by_data_type"]:
        frameworks.update(APPLICABILITY["by_data_type"][data_type])
    
    if region and region in APPLICABILITY["by_region"]:
        frameworks.update(APPLICABILITY["by_region"][region])
    
    return list(frameworks)


def get_strictest_breach_timeline(frameworks: List[ComplianceFramework]) -> Optional[timedelta]:
    """Get the shortest breach notification timeline"""
    timelines = []
    for fw in frameworks:
        timeline = get_breach_timeline(fw, "authority")
        if timeline:
            timelines.append(timeline)
    
    return min(timelines) if timelines else None


def get_framework_summary(framework: ComplianceFramework) -> Dict:
    """Get summary information about a framework"""
    return FRAMEWORK_REQUIREMENTS.get(framework, {})


# Export
__all__ = [
    "ComplianceFramework",
    "BREACH_TIMELINES",
    "FRAMEWORK_REQUIREMENTS",
    "get_breach_timeline",
    "get_applicable_frameworks", 
    "get_strictest_breach_timeline",
    "get_framework_summary"
]