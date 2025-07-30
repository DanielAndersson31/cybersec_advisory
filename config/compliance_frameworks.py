"""
Compliance frameworks configuration for cybersecurity regulations.
Defines regulatory requirements, timelines, and compliance mappings.
"""

from typing import Dict, List, Any, Optional, Set
from enum import Enum
from dataclasses import dataclass, field
from datetime import timedelta


class ComplianceFramework(Enum):
    """Supported compliance frameworks"""
    GDPR = "gdpr"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"
    SOX = "sox"
    ISO_27001 = "iso_27001"
    NIST = "nist"
    CCPA = "ccpa"
    GLBA = "glba"
    FERPA = "ferpa"
    FISMA = "fisma"


class DataCategory(Enum):
    """Categories of data with different protection requirements"""
    PERSONAL_DATA = "personal_data"
    SENSITIVE_PERSONAL = "sensitive_personal"
    HEALTH_INFORMATION = "health_information"
    FINANCIAL_DATA = "financial_data"
    PAYMENT_CARD = "payment_card"
    STUDENT_RECORDS = "student_records"
    GOVERNMENT_DATA = "government_data"


@dataclass
class BreachNotification:
    """Breach notification requirements"""
    authority_notification: Optional[timedelta]  # Time to notify authorities
    individual_notification: Optional[timedelta]  # Time to notify affected individuals
    public_notification: Optional[timedelta] = None  # Time for public disclosure
    threshold: str = "risk_based"  # When notification is required
    documentation_required: List[str] = field(default_factory=list)
    exceptions: List[str] = field(default_factory=list)  # When notification not required


@dataclass
class FrameworkRequirements:
    """Complete requirements for a compliance framework"""
    name: str
    full_name: str
    framework_id: ComplianceFramework
    jurisdiction: List[str]  # Geographic applicability
    sector: List[str]  # Industry sectors
    data_categories: List[DataCategory]  # Types of data covered
    breach_notification: BreachNotification
    key_requirements: List[str]
    penalties: Dict[str, str]
    assessment_frequency: str
    documentation_requirements: List[str]
    technical_controls: List[str]
    administrative_controls: List[str]
    certification_available: bool = False
    audit_required: bool = True
    implementation_timeline: Optional[str] = None


# GDPR Configuration
GDPR_CONFIG = FrameworkRequirements(
    name="GDPR",
    full_name="General Data Protection Regulation",
    framework_id=ComplianceFramework.GDPR,
    jurisdiction=["European Union", "EEA", "UK"],
    sector=["all"],
    data_categories=[DataCategory.PERSONAL_DATA, DataCategory.SENSITIVE_PERSONAL],
    breach_notification=BreachNotification(
        authority_notification=timedelta(hours=72),
        individual_notification=timedelta(days=30),
        threshold="high_risk_to_rights",
        documentation_required=[
            "Nature of the breach",
            "Categories and approximate number of data subjects",
            "Categories and approximate number of records",
            "Likely consequences",
            "Measures taken or proposed",
            "Contact details of DPO"
        ],
        exceptions=[
            "Encryption with secure key management",
            "No risk to rights and freedoms",
            "Disproportionate effort for individual notification"
        ]
    ),
    key_requirements=[
        "Lawful basis for processing",
        "Data Protection by Design and Default",
        "Right to Access (Subject Access Requests)",
        "Right to Erasure (Right to be Forgotten)",
        "Right to Data Portability",
        "Right to Rectification",
        "Privacy Impact Assessments (DPIA)",
        "Data Protection Officer appointment (if required)",
        "Cross-border transfer mechanisms"
    ],
    penalties={
        "maximum": "€20 million or 4% of annual global turnover",
        "serious_infringement": "€10 million or 2% of annual global turnover",
        "factors": "Nature, gravity, duration, intentional/negligent, categories of data"
    },
    assessment_frequency="ongoing with annual review",
    documentation_requirements=[
        "Records of processing activities (Article 30)",
        "Privacy notices/policies",
        "Consent records and mechanisms",
        "Data Protection Impact Assessments",
        "Third-party processor agreements",
        "Cross-border transfer documentation",
        "Training records",
        "Incident response logs"
    ],
    technical_controls=[
        "Encryption at rest and in transit",
        "Pseudonymization where appropriate",
        "Access controls and authentication",
        "Regular security testing",
        "Data loss prevention (DLP)",
        "Backup and recovery procedures",
        "System and event logging",
        "Vulnerability management"
    ],
    administrative_controls=[
        "Privacy governance program",
        "Employee privacy training",
        "Incident response procedures",
        "Vendor management program",
        "Data retention and disposal policies",
        "Privacy by Design procedures",
        "Subject rights fulfillment process"
    ],
    certification_available=True,
    audit_required=True
)


# HIPAA Configuration
HIPAA_CONFIG = FrameworkRequirements(
    name="HIPAA",
    full_name="Health Insurance Portability and Accountability Act",
    framework_id=ComplianceFramework.HIPAA,
    jurisdiction=["United States"],
    sector=["healthcare", "health_plans", "healthcare_clearinghouses", "business_associates"],
    data_categories=[DataCategory.HEALTH_INFORMATION],
    breach_notification=BreachNotification(
        authority_notification=timedelta(days=60),
        individual_notification=timedelta(days=60),
        public_notification=timedelta(days=60),  # If >500 individuals
        threshold="unsecured_phi",
        documentation_required=[
            "Date of breach discovery",
            "Description of PHI involved",
            "Steps individuals should take",
            "What covered entity is doing",
            "Contact information"
        ],
        exceptions=[
            "Encrypted data meeting NIST standards",
            "Unintentional access by authorized person",
            "Good faith belief information not retained"
        ]
    ),
    key_requirements=[
        "Administrative Safeguards",
        "Physical Safeguards", 
        "Technical Safeguards",
        "Business Associate Agreements (BAA)",
        "Minimum Necessary Standard",
        "Access Controls",
        "Audit Controls",
        "Transmission Security",
        "Risk Assessments"
    ],
    penalties={
        "minimum": "$100 per violation",
        "maximum": "$2 million per violation type per year",
        "criminal": "Up to $250,000 and 10 years imprisonment",
        "tiers": "Based on culpability level (unknowing to willful neglect)"
    },
    assessment_frequency="annual with ongoing monitoring",
    documentation_requirements=[
        "Risk assessments and management plans",
        "Policies and procedures",
        "Business Associate Agreements",
        "Training documentation",
        "Incident response documentation",
        "Access logs and audit trails",
        "Authorization forms",
        "Workforce training records"
    ],
    technical_controls=[
        "Access control (unique user ID, encryption, automatic logoff)",
        "Audit logs and monitoring",
        "Integrity controls",
        "Transmission security (encryption)",
        "Encryption at rest for ePHI"
    ],
    administrative_controls=[
        "Security Officer designation",
        "Workforce training program",
        "Access management procedures",
        "Incident response plan",
        "Business Associate management",
        "Contingency planning",
        "Regular risk assessments"
    ],
    certification_available=False,
    audit_required=True
)


# PCI-DSS Configuration
PCI_DSS_CONFIG = FrameworkRequirements(
    name="PCI-DSS",
    full_name="Payment Card Industry Data Security Standard",
    framework_id=ComplianceFramework.PCI_DSS,
    jurisdiction=["Global"],
    sector=["any_processing_payment_cards"],
    data_categories=[DataCategory.PAYMENT_CARD],
    breach_notification=BreachNotification(
        authority_notification=timedelta(hours=24),  # To card brands
        individual_notification=None,  # Determined by card brands
        threshold="any_compromise",
        documentation_required=[
            "Forensic investigation report",
            "Root cause analysis",
            "Remediation timeline",
            "Evidence of containment"
        ]
    ),
    key_requirements=[
        "Build and Maintain Secure Network",
        "Protect Cardholder Data",
        "Maintain Vulnerability Management Program",
        "Implement Strong Access Control",
        "Regular Security Testing",
        "Information Security Policy",
        "Network Segmentation",
        "Encryption of Cardholder Data",
        "Quarterly Vulnerability Scans"
    ],
    penalties={
        "fines": "$5,000 to $100,000 per month",
        "termination": "Loss of card processing privileges",
        "liability": "Fraud liability shift to merchant",
        "forensic_costs": "Merchant bears investigation costs"
    },
    assessment_frequency="annual with quarterly scans",
    documentation_requirements=[
        "Self-Assessment Questionnaire (SAQ) or Report on Compliance (ROC)",
        "Attestation of Compliance (AOC)",
        "Quarterly scan reports",
        "Penetration test results",
        "Security policies and procedures",
        "Risk assessment documentation",
        "Incident response plan",
        "Change control records"
    ],
    technical_controls=[
        "Firewall configuration",
        "No vendor defaults",
        "Encrypted transmission",
        "Encrypted storage",
        "Anti-virus/anti-malware",
        "Secure development",
        "Access control",
        "Multi-factor authentication",
        "Logging and monitoring"
    ],
    administrative_controls=[
        "Security awareness training",
        "Background checks",
        "Incident response procedures",
        "Vendor management",
        "Physical security controls",
        "Media handling procedures",
        "Regular security testing"
    ],
    certification_available=True,
    audit_required=True,
    implementation_timeline="Immediate upon processing cards"
)


# SOX Configuration
SOX_CONFIG = FrameworkRequirements(
    name="SOX",
    full_name="Sarbanes-Oxley Act",
    framework_id=ComplianceFramework.SOX,
    jurisdiction=["United States"],
    sector=["public_companies", "accounting_firms"],
    data_categories=[DataCategory.FINANCIAL_DATA],
    breach_notification=BreachNotification(
        authority_notification=timedelta(days=4),  # Material events
        individual_notification=None,
        threshold="material_impact",
        documentation_required=[
            "8-K filing for material events",
            "Internal control assessment",
            "Management disclosure"
        ]
    ),
    key_requirements=[
        "Internal Controls over Financial Reporting (ICFR)",
        "IT General Controls (ITGC)",
        "Management Assessment of Controls",
        "External Auditor Assessment",
        "CEO/CFO Certification",
        "Audit Committee Independence",
        "Document Retention",
        "Whistleblower Protection"
    ],
    penalties={
        "criminal": "Up to 20 years imprisonment",
        "fines": "Up to $5 million for individuals",
        "corporate": "Up to $25 million for companies",
        "certification_false": "Up to $5 million and 20 years"
    },
    assessment_frequency="annual with quarterly reviews",
    documentation_requirements=[
        "Control documentation",
        "Risk assessment",
        "Testing procedures and results",
        "Deficiency tracking",
        "Management certifications",
        "Audit trail documentation",
        "Change management records",
        "Access control documentation"
    ],
    technical_controls=[
        "Access controls and segregation of duties",
        "Change management controls",
        "System operation controls",
        "Backup and recovery",
        "Security monitoring",
        "Data integrity controls"
    ],
    administrative_controls=[
        "IT governance framework",
        "Risk assessment process",
        "Control testing procedures",
        "Documentation standards",
        "Training programs",
        "Incident management",
        "Vendor management"
    ],
    certification_available=False,
    audit_required=True
)


# Centralized framework registry
FRAMEWORKS: Dict[ComplianceFramework, FrameworkRequirements] = {
    ComplianceFramework.GDPR: GDPR_CONFIG,
    ComplianceFramework.HIPAA: HIPAA_CONFIG,
    ComplianceFramework.PCI_DSS: PCI_DSS_CONFIG,
    ComplianceFramework.SOX: SOX_CONFIG,
}


# Framework applicability matrix
FRAMEWORK_APPLICABILITY = {
    "by_region": {
        "European Union": [ComplianceFramework.GDPR],
        "United States": [ComplianceFramework.HIPAA, ComplianceFramework.SOX, ComplianceFramework.CCPA],
        "California": [ComplianceFramework.CCPA],
        "Global": [ComplianceFramework.PCI_DSS, ComplianceFramework.ISO_27001],
    },
    "by_data_type": {
        DataCategory.PERSONAL_DATA: [ComplianceFramework.GDPR, ComplianceFramework.CCPA],
        DataCategory.HEALTH_INFORMATION: [ComplianceFramework.HIPAA],
        DataCategory.PAYMENT_CARD: [ComplianceFramework.PCI_DSS],
        DataCategory.FINANCIAL_DATA: [ComplianceFramework.SOX, ComplianceFramework.GLBA],
    },
    "by_industry": {
        "healthcare": [ComplianceFramework.HIPAA],
        "financial": [ComplianceFramework.SOX, ComplianceFramework.GLBA, ComplianceFramework.PCI_DSS],
        "retail": [ComplianceFramework.PCI_DSS, ComplianceFramework.GDPR],
        "technology": [ComplianceFramework.GDPR, ComplianceFramework.CCPA, ComplianceFramework.ISO_27001],
    }
}


# Breach severity classification
BREACH_SEVERITY = {
    "critical": {
        "description": "Large-scale breach with sensitive data",
        "criteria": [
            "Over 10,000 records affected",
            "Sensitive personal data involved",
            "Financial data compromised",
            "Ongoing unauthorized access"
        ],
        "response_time": "immediate"
    },
    "high": {
        "description": "Significant breach requiring urgent action",
        "criteria": [
            "1,000-10,000 records affected",
            "Personal data involved",
            "Contained but significant impact"
        ],
        "response_time": "within 24 hours"
    },
    "medium": {
        "description": "Moderate breach with limited impact",
        "criteria": [
            "100-1,000 records affected",
            "Non-sensitive personal data",
            "Quickly contained"
        ],
        "response_time": "within 72 hours"
    },
    "low": {
        "description": "Minor incident with minimal impact",
        "criteria": [
            "Under 100 records",
            "Encrypted or anonymized data",
            "No actual access confirmed"
        ],
        "response_time": "standard timeline"
    }
}


# Helper functions
def get_framework(framework_id: ComplianceFramework) -> Optional[FrameworkRequirements]:
    """Get framework requirements by ID"""
    return FRAMEWORKS.get(framework_id)


def get_applicable_frameworks(
    region: Optional[str] = None,
    data_type: Optional[DataCategory] = None,
    industry: Optional[str] = None
) -> Set[ComplianceFramework]:
    """Get frameworks applicable to given criteria"""
    applicable = set()
    
    if region:
        applicable.update(FRAMEWORK_APPLICABILITY["by_region"].get(region, []))
    
    if data_type:
        applicable.update(FRAMEWORK_APPLICABILITY["by_data_type"].get(data_type, []))
    
    if industry:
        applicable.update(FRAMEWORK_APPLICABILITY["by_industry"].get(industry, []))
    
    # If no criteria specified, return all frameworks
    if not any([region, data_type, industry]):
        applicable.update(FRAMEWORKS.keys())
    
    return applicable


def get_breach_notification_timeline(
    framework_id: ComplianceFramework,
    notification_type: str = "authority"
) -> Optional[timedelta]:
    """Get breach notification timeline for a framework"""
    framework = get_framework(framework_id)
    if not framework:
        return None
    
    breach_notif = framework.breach_notification
    if notification_type == "authority":
        return breach_notif.authority_notification
    elif notification_type == "individual":
        return breach_notif.individual_notification
    elif notification_type == "public":
        return breach_notif.public_notification
    
    return None


def get_strictest_timeline(
    frameworks: List[ComplianceFramework],
    notification_type: str = "authority"
) -> Optional[timedelta]:
    """Get the strictest (shortest) timeline from multiple frameworks"""
    timelines = []
    
    for fw_id in frameworks:
        timeline = get_breach_notification_timeline(fw_id, notification_type)
        if timeline:
            timelines.append(timeline)
    
    return min(timelines) if timelines else None


def assess_breach_severity(
    records_affected: int,
    data_types: List[DataCategory],
    contained: bool = False
) -> str:
    """Assess breach severity based on criteria"""
    # Critical if sensitive data and large scale
    if (records_affected > 10000 or 
        DataCategory.FINANCIAL_DATA in data_types or
        DataCategory.HEALTH_INFORMATION in data_types):
        return "critical"
    
    # High if significant records
    if records_affected > 1000:
        return "high"
    
    # Medium if moderate records
    if records_affected > 100:
        return "medium"
    
    # Low otherwise
    return "low"


def get_combined_requirements(
    frameworks: List[ComplianceFramework]
) -> Dict[str, Any]:
    """Get combined requirements for multiple frameworks"""
    combined = {
        "technical_controls": set(),
        "administrative_controls": set(),
        "documentation": set(),
        "breach_timeline": None,
        "frameworks": []
    }
    
    for fw_id in frameworks:
        framework = get_framework(fw_id)
        if framework:
            combined["technical_controls"].update(framework.technical_controls)
            combined["administrative_controls"].update(framework.administrative_controls)
            combined["documentation"].update(framework.documentation_requirements)
            combined["frameworks"].append(framework.name)
    
    # Get strictest breach timeline
    combined["breach_timeline"] = get_strictest_timeline(frameworks)
    
    # Convert sets to lists for JSON serialization
    combined["technical_controls"] = list(combined["technical_controls"])
    combined["administrative_controls"] = list(combined["administrative_controls"])
    combined["documentation"] = list(combined["documentation"])
    
    return combined


# Export key components
__all__ = [
    "ComplianceFramework",
    "DataCategory",
    "BreachNotification",
    "FrameworkRequirements",
    "FRAMEWORKS",
    "FRAMEWORK_APPLICABILITY",
    "BREACH_SEVERITY",
    "get_framework",
    "get_applicable_frameworks",
    "get_breach_notification_timeline",
    "get_strictest_timeline",
    "assess_breach_severity",
    "get_combined_requirements"
]