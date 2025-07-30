"""
Agent configuration settings for the cybersecurity multi-agent system.
This file contains high-level configurations and mappings.
Detailed implementations are in the agents/ folder.
"""

from typing import Dict, List, Any
from enum import Enum
from config.settings import settings


class AgentRole(Enum):
    """Agent role identifiers used throughout the system"""
    INCIDENT_RESPONSE = "incident_response"
    PREVENTION = "prevention"
    THREAT_INTEL = "threat_intel"
    COMPLIANCE = "compliance"
    COORDINATOR = "coordinator"


# Agent basic configurations
AGENT_CONFIGS = {
    "incident_response": {
        "name": "Sarah Chen",
        "role": AgentRole.INCIDENT_RESPONSE,
        "model": settings.DEFAULT_MODEL,
        "temperature": 0.1,
        "max_tokens": 2000,
        "timeout": 30,
        "retry_attempts": 3,
        "confidence_threshold": 0.85,
        "interruption_threshold": 0.9,
        "enabled": True
    },
    "prevention": {
        "name": "Alex Rodriguez",
        "role": AgentRole.PREVENTION,
        "model": settings.DEFAULT_MODEL,
        "temperature": 0.2,
        "max_tokens": 2000,
        "timeout": 30,
        "retry_attempts": 3,
        "confidence_threshold": 0.75,
        "interruption_threshold": 0.7,
        "enabled": True
    },
    "threat_intel": {
        "name": "Dr. Kim Park",
        "role": AgentRole.THREAT_INTEL,
        "model": settings.DEFAULT_MODEL,
        "temperature": 0.15,
        "max_tokens": 2000,
        "timeout": 45,  # More time for research
        "retry_attempts": 3,
        "confidence_threshold": 0.8,
        "interruption_threshold": 0.75,
        "enabled": True
    },
    "compliance": {
        "name": "Maria Santos",
        "role": AgentRole.COMPLIANCE,
        "model": settings.DEFAULT_MODEL,
        "temperature": 0.05,
        "max_tokens": 2500,  # Compliance responses can be longer
        "timeout": 30,
        "retry_attempts": 3,
        "confidence_threshold": 0.9,  # Highest confidence for compliance
        "interruption_threshold": 0.85,
        "enabled": True
    },
    "coordinator": {
        "name": "Team Coordinator",
        "role": AgentRole.COORDINATOR,
        "model": settings.DEFAULT_MODEL,
        "temperature": 0.3,
        "max_tokens": 1000,
        "timeout": 20,
        "retry_attempts": 2,
        "confidence_threshold": 0.7,
        "interruption_threshold": 0.5,
        "enabled": True
    }
}


# Tool permissions mapping
AGENT_TOOL_PERMISSIONS = {
    AgentRole.INCIDENT_RESPONSE: [
        "analyze_indicators",
        "search_vulnerabilities",
        "forensics_tools",
        "incident_playbooks",
        "web_search",
        "knowledge_search"
    ],
    AgentRole.PREVENTION: [
        "search_vulnerabilities",
        "security_benchmarks",
        "architecture_patterns",
        "compliance_check",
        "web_search",
        "knowledge_search"
    ],
    AgentRole.THREAT_INTEL: [
        "analyze_indicators",
        "threat_feeds",
        "attribution_db",
        "mitre_attack",
        "web_search",
        "knowledge_search"
    ],
    AgentRole.COMPLIANCE: [
        "compliance_check",
        "regulation_db",
        "audit_tools",
        "policy_templates",
        "web_search",
        "knowledge_search"
    ],
    AgentRole.COORDINATOR: [
        "web_search",
        "knowledge_search"
    ]
}


# Agent interaction rules
INTERACTION_RULES = {
    "speaking_order": [
        AgentRole.INCIDENT_RESPONSE,
        AgentRole.THREAT_INTEL,
        AgentRole.PREVENTION,
        AgentRole.COMPLIANCE
    ],
    "handoff_triggers": {
        "forensics_needed": AgentRole.INCIDENT_RESPONSE,
        "architecture_review": AgentRole.PREVENTION,
        "attribution_required": AgentRole.THREAT_INTEL,
        "compliance_check": AgentRole.COMPLIANCE
    },
    "consensus_requirements": {
        "critical_decisions": 3,  # Number of agents that must agree
        "standard_decisions": 2,
        "informational": 1
    }
}


# Response time limits (in seconds)
RESPONSE_TIME_LIMITS = {
    "emergency": 10,
    "urgent": 30,
    "normal": 60,
    "research": 120
}


# Quality thresholds
QUALITY_THRESHOLDS = {
    AgentRole.INCIDENT_RESPONSE: 7.5,
    AgentRole.PREVENTION: 7.0,
    AgentRole.THREAT_INTEL: 7.5,
    AgentRole.COMPLIANCE: 8.0,
    AgentRole.COORDINATOR: 6.0
}


# Agent expertise domains (for knowledge routing)
EXPERTISE_DOMAINS = {
    AgentRole.INCIDENT_RESPONSE: [
        "incident_handling",
        "forensics",
        "malware_analysis",
        "crisis_management"
    ],
    AgentRole.PREVENTION: [
        "security_architecture",
        "vulnerability_management",
        "secure_design",
        "risk_mitigation"
    ],
    AgentRole.THREAT_INTEL: [
        "threat_analysis",
        "attribution",
        "threat_hunting",
        "intelligence_gathering"
    ],
    AgentRole.COMPLIANCE: [
        "regulatory_compliance",
        "audit",
        "governance",
        "policy_management"
    ]
}


# Helper functions
def get_agent_config(role: AgentRole) -> Dict[str, Any]:
    """Get configuration for a specific agent role"""
    for config in AGENT_CONFIGS.values():
        if config["role"] == role:
            return config
    raise ValueError(f"No configuration found for role: {role}")


def get_agent_tools(role: AgentRole) -> List[str]:
    """Get allowed tools for an agent role"""
    return AGENT_TOOL_PERMISSIONS.get(role, [])


def get_quality_threshold(role: AgentRole) -> float:
    """Get quality threshold for an agent role"""
    return QUALITY_THRESHOLDS.get(role, 7.0)


def get_enabled_agents() -> List[Dict[str, Any]]:
    """Get list of all enabled agent configurations"""
    return [
        config for config in AGENT_CONFIGS.values()
        if config.get("enabled", True)
    ]


def get_agent_by_name(name: str) -> Dict[str, Any]:
    """Get agent configuration by name"""
    for config in AGENT_CONFIGS.values():
        if config["name"].lower() == name.lower():
            return config
    raise ValueError(f"No agent found with name: {name}")


# Conversation configuration
CONVERSATION_CONFIG = {
    "max_rounds": 10,
    "min_confidence_for_conclusion": 0.7,
    "enable_interruptions": True,
    "enable_corrections": True,
    "log_conversations": True,
    "save_checkpoints": True
}


# Export configurations
__all__ = [
    "AgentRole",
    "AGENT_CONFIGS",
    "AGENT_TOOL_PERMISSIONS",
    "INTERACTION_RULES",
    "RESPONSE_TIME_LIMITS",
    "QUALITY_THRESHOLDS",
    "EXPERTISE_DOMAINS",
    "CONVERSATION_CONFIG",
    "get_agent_config",
    "get_agent_tools",
    "get_quality_threshold",
    "get_enabled_agents",
    "get_agent_by_name"
]