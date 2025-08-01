"""
Simplified MCP configuration for server coordination and client connections.
"""

from typing import Dict, Any, List
from config.settings import settings

# Server network configurations
MCP_SERVERS = {
    "cybersec_tools": {
        "name": "General Cybersecurity Tools",
        "host": settings.MCP_HOST,
        "port": settings.MCP_PORT,  # 8080
        "timeout": 30,
        "description": "Web search, knowledge base, general tools"
    },
    "incident_tools": {
        "name": "Incident Response Tools",
        "host": settings.MCP_HOST,
        "port": 8081,
        "timeout": 45,  # Longer for forensics
        "description": "IOC analysis, forensics, timeline extraction"
    },
    "prevention_tools": {
        "name": "Prevention & Architecture Tools",
        "host": settings.MCP_HOST,
        "port": 8082,
        "timeout": 30,
        "description": "Vulnerability search, security benchmarks"
    },
    "threat_intel": {
        "name": "Threat Intelligence Tools",
        "host": settings.MCP_HOST,
        "port": 8083,
        "timeout": 60,  # Longer for intel gathering
        "description": "Threat feeds, attribution, MITRE ATT&CK"
    },
    "compliance_tools": {
        "name": "Compliance & GRC Tools",
        "host": settings.MCP_HOST,
        "port": 8084,
        "timeout": 30,
        "description": "Compliance checks, regulation lookup"
    }
}

# Client connection settings
CLIENT_CONFIG = {
    "retry": {
        "max_attempts": 3,
        "base_delay": 1.0,
        "max_delay": 10.0,
        "retry_on_status_codes": [502, 503, 504],
    },
    "connection_pool": {
        "max_connections": 10,
        "max_keepalive": 5,
        "timeout": 5.0,
    },
    "default_timeout": 30.0
}

# Tool categories for agent permissions
TOOL_CATEGORIES = {
    "forensics": ["analyze_indicators", "timeline_analysis", "memory_analysis"],
    "threat_intelligence": ["threat_feed_search", "attribution_lookup", "mitre_attack_search"],
    "vulnerability": ["search_vulnerabilities", "scan_configuration"],
    "compliance": ["compliance_check", "regulation_lookup", "breach_calculator"],
    "general": ["web_search", "knowledge_search"]
}

# Helper functions
def get_server_url(server_name: str) -> str:
    """Get full URL for a server"""
    server = MCP_SERVERS.get(server_name)
    if server:
        return f"http://{server['host']}:{server['port']}"
    return None

def get_all_server_urls() -> Dict[str, str]:
    """Get URLs for all servers"""
    return {
        name: get_server_url(name)
        for name in MCP_SERVERS.keys()
    }

def get_server_info(server_name: str) -> Dict[str, Any]:
    """Get server configuration"""
    return MCP_SERVERS.get(server_name, {})

# Validation
def validate_ports() -> bool:
    """Check for port conflicts"""
    ports = [s["port"] for s in MCP_SERVERS.values()]
    return len(ports) == len(set(ports))

# Export what's actually needed
__all__ = [
    "MCP_SERVERS",
    "CLIENT_CONFIG", 
    "TOOL_CATEGORIES",
    "get_server_url",
    "get_all_server_urls"
]