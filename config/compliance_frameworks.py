"""
Compliance frameworks configuration data.
Pure configuration - no business logic.
"""

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


# Breach notification timelines
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
        "authority": timedelta(hours=24),
        "individuals": None,
        "threshold": "any cardholder data compromise"
    },
    ComplianceFramework.SOX: {
        "authority": timedelta(days=4),
        "individuals": None,
        "threshold": "material financial impact"
    }
}


# Framework requirements and details
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


# Framework applicability mapping
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