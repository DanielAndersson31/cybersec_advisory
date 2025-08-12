"""
Agent configuration settings for the cybersecurity multi-agent system.
This file contains high-level configurations, tool definitions, and mappings.
Detailed implementations are in the agents/ folder.
"""

from typing import Dict, List, Any
from enum import Enum
from .settings import settings


class AgentRole(Enum):
    """Agent role identifiers used throughout the system"""
    INCIDENT_RESPONSE = "incident_response"
    PREVENTION = "prevention"
    THREAT_INTEL = "threat_intel"
    COMPLIANCE = "compliance"
    COORDINATOR = "coordinator"


AGENT_CONFIGS = {
    AgentRole.INCIDENT_RESPONSE: {
        "name": "Sarah Chen (Incident Response)",
        "role": AgentRole.INCIDENT_RESPONSE,
        "model": settings.default_model,
        "temperature": 0.1,
        "max_tokens": 3000,
        "timeout": 30,
        "retry_attempts": 3,
        "confidence_threshold": 0.85,
        "interruption_threshold": 0.9,
        "enabled": True
    },
    AgentRole.PREVENTION: {
        "name": "Alex Rodriguez (Prevention)",
        "role": AgentRole.PREVENTION,
        "model": settings.default_model,
        "temperature": 0.2,
        "max_tokens": 3000,
        "timeout": 30,
        "retry_attempts": 3,
        "confidence_threshold": 0.75,
        "interruption_threshold": 0.7,
        "enabled": True
    },
    AgentRole.THREAT_INTEL: {
        "name": "Dr. Kim Park (Threat Intel)",
        "role": AgentRole.THREAT_INTEL,
        "model": settings.default_model,
        "temperature": 0.3,
        "max_tokens": 3500,
        "timeout": 45,
        "retry_attempts": 3,
        "confidence_threshold": 0.8,
        "interruption_threshold": 0.75,
        "enabled": True
    },
    AgentRole.COMPLIANCE: {
        "name": "Maria Santos (Compliance)",
        "role": AgentRole.COMPLIANCE,
        "model": settings.default_model,
        "temperature": 0.0,
        "max_tokens": 2500,
        "timeout": 30,
        "retry_attempts": 3,
        "confidence_threshold": 0.9,
        "interruption_threshold": 0.85,
        "enabled": True
    },
    AgentRole.COORDINATOR: {
        "name": "Team Coordinator",
        "role": AgentRole.COORDINATOR,
        "model": settings.default_model,
        "temperature": 0.3,
        "max_tokens": 1000,
        "timeout": 20,
        "retry_attempts": 2,
        "confidence_threshold": 0.7,
        "interruption_threshold": 0.5,
        "enabled": True
    }
}


TOOL_DEFINITIONS = {
    "ioc_analysis_tool": {
        "name": "ioc_analysis_tool",
        "description": "Analyzes a specific Indicator of Compromise (IOC) like an IP address, domain, or file hash to determine if it is malicious and get context.",
        "parameters": { "type": "object", "properties": { "indicator": { "type": "string", "description": "The IOC to analyze, e.g., '1.2.3.4' or 'badsite.com."}}, "required": ["indicator"]}
    },
    "vulnerability_search_tool": {
        "name": "vulnerability_search_tool",
        "description": "Searches for details on a Common Vulnerabilities and Exposures (CVE) ID to find its severity, impacted systems, and available patches.",
        "parameters": { "type": "object", "properties": { "cve_id": { "type": "string", "description": "The CVE identifier, e.g., 'CVE-2023-12345'."}}, "required": ["cve_id"]}
    },
    "web_search_tool": {
        "name": "web_search_tool",
        "description": "Performs a web search to find up-to-date information on cybersecurity news, emerging threats, or technical topics.",
        "parameters": { "type": "object", "properties": { "query": { "type": "string", "description": "The search query."}}, "required": ["query"]}
    },
    "knowledge_search_tool": {
        "name": "knowledge_search_tool",
        "description": "Searches the internal knowledge base for company-specific documents like playbooks, policies, and post-incident reports.",
        "parameters": { "type": "object", "properties": { "query": { "type": "string", "description": "The topic or keyword to search for in the knowledge base."}}, "required": ["query"]}
    },
    "exposure_checker_tool": {
        "name": "exposure_checker_tool",
        "description": "Checks if an email address has been exposed in a data breach.",
        "parameters": {
            "type": "object",
            "properties": {
                "email": { "type": "string", "description": "The email address to check for exposure."}
            },
            "required": ["email"]
        }
    },
    "attack_surface_analyzer_tool": {
        "name": "attack_surface_analyzer_tool",
        "description": "Analyzes a company's domain to identify exposed assets, open ports, and potential vulnerabilities visible from the internet.",
        "parameters": { "type": "object", "properties": { "domain": { "type": "string", "description": "The company's primary domain to analyze."}}, "required": ["domain"]}
    },
    "threat_feeds_tool": {
        "name": "threat_feeds_tool",
        "description": "Queries subscribed threat intelligence feeds for information on threat actors, campaigns, tactics, techniques, and procedures (TTPs).",
        "parameters": { "type": "object", "properties": { "topic": { "type": "string", "description": "The threat actor, campaign, or TTP to research."}}, "required": ["topic"]}
    },
    "compliance_guidance_tool": {
        "name": "compliance_guidance_tool",
        "description": "Provides guidance on specific regulatory compliance frameworks like GDPR, HIPAA, or PCI-DSS based on a query.",
        "parameters": { "type": "object", "properties": { "framework": { "type": "string", "description": "The compliance framework, e.g., 'GDPR'."}, "query": { "type": "string", "description": "The specific compliance question."}}, "required": ["framework", "query"]}
    }
}


AGENT_TOOL_PERMISSIONS = {
    AgentRole.INCIDENT_RESPONSE: [
        "ioc_analysis_tool",
        "vulnerability_search_tool",
        "web_search_tool",
        "knowledge_search_tool",
        "exposure_checker_tool"
    ],
    AgentRole.PREVENTION: [
        "vulnerability_search_tool",
        "attack_surface_analyzer_tool",
        "web_search_tool",
        "knowledge_search_tool"
    ],
    AgentRole.THREAT_INTEL: [
        "ioc_analysis_tool",
        "threat_feeds_tool",
        "web_search_tool",
        "knowledge_search_tool"
    ],
    AgentRole.COMPLIANCE: [
        "compliance_guidance_tool",
        "web_search_tool",
        "knowledge_search_tool"
    ],
    AgentRole.COORDINATOR: [
        "web_search_tool",
        "knowledge_search_tool"
    ]
}


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
        "critical_decisions": 3,
        "standard_decisions": 2,
        "informational": 1
    }
}


RESPONSE_TIME_LIMITS = {
    "emergency": 10,
    "urgent": 30,
    "normal": 60,
    "research": 120
}


QUALITY_THRESHOLDS = {
    AgentRole.INCIDENT_RESPONSE: 7.5,
    AgentRole.PREVENTION: 7.0,
    AgentRole.THREAT_INTEL: 7.5,
    AgentRole.COMPLIANCE: 8.0,
    AgentRole.COORDINATOR: 6.0
}


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


def get_agent_config(role: AgentRole) -> Dict[str, Any]:
    """Get configuration for a specific agent role"""
    if role not in AGENT_CONFIGS:
        raise ValueError(f"No configuration found for role: {role}")
    return AGENT_CONFIGS[role]


def get_agent_tools(role: AgentRole) -> List[Dict[str, Any]]:
    """
    Gets the full, correctly formatted tool definitions for an agent.
    Wraps the function definition with the required 'type: "function"' structure.
    """
    allowed_tool_names = AGENT_TOOL_PERMISSIONS.get(role, [])
    formatted_tools = []
    for tool_name in allowed_tool_names:
        if tool_name in TOOL_DEFINITIONS:
            tool_def = TOOL_DEFINITIONS[tool_name]
            # Wrap the existing definition in the required format
            formatted_tools.append({
                "type": "function",
                "function": tool_def
            })
    return formatted_tools


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


CONVERSATION_CONFIG = {
    "max_rounds": 10,
    "min_confidence_for_conclusion": 0.7,
    "enable_interruptions": True,
    "enable_corrections": True,
    "log_conversations": True,
    "save_checkpoints": True
}


__all__ = [
    "AgentRole",
    "AGENT_CONFIGS",
    "TOOL_DEFINITIONS",
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
