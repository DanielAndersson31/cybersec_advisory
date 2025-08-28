"""
Agent configuration settings for the cybersecurity multi-agent system.
This file contains high-level configurations, tool definitions, and mappings.
Detailed implementations are in the agents/ folder.
"""

from typing import Dict, List, Any
from enum import Enum

from langchain_core.tools import BaseTool
from .settings import settings
from cybersec_mcp.cybersec_tools import CybersecurityToolkit


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
    "ioc_analysis": {
        "name": "ioc_analysis",
        "description": "Analyzes a specific Indicator of Compromise (IOC) like an IP address, domain, or file hash to determine if it is malicious and get context.",
        "parameters": { "type": "object", "properties": { "indicator": { "type": "string", "description": "The IOC to analyze, e.g., '1.2.3.4' or 'badsite.com."}}, "required": ["indicator"]}
    },
    "vulnerability_search": {
        "name": "vulnerability_search",
        "description": "Searches for details on a Common Vulnerabilities and Exposures (CVE) ID to find its severity, impacted systems, and available patches.",
        "parameters": { "type": "object", "properties": { "query": { "type": "string", "description": "The CVE identifier or search query, e.g., 'CVE-2023-12345' or 'Apache Log4j'."}}, "required": ["query"]}
    },
    "web_search": {
        "name": "web_search",
        "description": "Performs a web search to find up-to-date information on cybersecurity news, emerging threats, or technical topics.",
        "parameters": { "type": "object", "properties": { "query": { "type": "string", "description": "The search query."}}, "required": ["query"]}
    },
    "knowledge_search": {
        "name": "knowledge_search",
        "description": "Searches the internal knowledge base for company-specific documents like playbooks, policies, and post-incident reports.",
        "parameters": { "type": "object", "properties": { "query": { "type": "string", "description": "The topic or keyword to search for in the knowledge base."}}, "required": ["query"]}
    },
    "exposure_checker": {
        "name": "exposure_checker",
        "description": "Checks if an email address has been exposed in a data breach.",
        "parameters": {
            "type": "object",
            "properties": {
                "email": { "type": "string", "description": "The email address to check for exposure."}
            },
            "required": ["email"]
        }
    },
    "threat_feeds": {
        "name": "threat_feeds",
        "description": "Queries subscribed threat intelligence feeds for information on threat actors, campaigns, tactics, techniques, and procedures (TTPs).",
        "parameters": { "type": "object", "properties": { "query": { "type": "string", "description": "The threat actor, campaign, or TTP to research."}, "limit": { "type": "integer", "description": "Maximum number of results to return (default: 5)."}, "fetch_full_details": { "type": "boolean", "description": "Whether to fetch full details including IOCs (default: false)."}}, "required": ["query"]}
    },
    "compliance_guidance": {
        "name": "compliance_guidance",
        "description": "Provides guidance on specific regulatory compliance frameworks like GDPR, HIPAA, or PCI-DSS based on a query.",
        "parameters": { "type": "object", "properties": { "framework": { "type": "string", "description": "The compliance framework, e.g., 'GDPR'."}, "data_type": { "type": "string", "description": "Type of data involved, e.g., 'personal_data', 'health_data'."}, "region": { "type": "string", "description": "Geographic region, e.g., 'EU', 'US'."}, "incident_type": { "type": "string", "description": "Type of incident, e.g., 'breach', 'vulnerability'."}}, "required": ["framework"]}
    }
}


AGENT_TOOL_PERMISSIONS = {
    AgentRole.INCIDENT_RESPONSE: [
        "ioc_analysis",
        "web_search",
        "knowledge_search",
        "exposure_checker",
    ],
    AgentRole.PREVENTION: [
        "vulnerability_search",
        "web_search",
        "knowledge_search",
        "threat_feeds"
    ],
    AgentRole.THREAT_INTEL: [
        "ioc_analysis",
        "threat_feeds",
        "web_search",
        "knowledge_search"
    ],
    AgentRole.COMPLIANCE: [
        "compliance_guidance",
        "web_search",
        "knowledge_search"
    ],
    AgentRole.COORDINATOR: [
        "knowledge_search"
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
    AgentRole.INCIDENT_RESPONSE: 6.0,  # Enhanced evaluation with context awareness
    AgentRole.PREVENTION: 5.5,         # Enhanced evaluation with strategic thinking
    AgentRole.THREAT_INTEL: 6.0,       # Enhanced evaluation with intelligence quality
    AgentRole.COMPLIANCE: 6.5,         # Enhanced evaluation with regulatory expertise
    AgentRole.COORDINATOR: 5.5,        # Enhanced evaluation
}


def get_agent_config(role: AgentRole) -> Dict[str, Any]:
    """Get configuration for a specific agent role"""
    if role not in AGENT_CONFIGS:
        raise ValueError(f"No configuration found for role: {role}")
    return AGENT_CONFIGS[role]


def get_agent_tools(role: AgentRole, toolkit: CybersecurityToolkit) -> List[BaseTool]:
    """
    Gets the permitted BaseTool objects for an agent's role.
    """
    allowed_tool_names = AGENT_TOOL_PERMISSIONS.get(role, [])
    agent_tools = []
    for tool_name in allowed_tool_names:
        tool = toolkit.get_tool_by_name(tool_name)
        if tool:
            agent_tools.append(tool)
    return agent_tools


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
    "CONVERSATION_CONFIG",
    "get_agent_config",
    "get_agent_tools",
    "get_quality_threshold",
    "get_enabled_agents",
    "get_agent_by_name"
]
