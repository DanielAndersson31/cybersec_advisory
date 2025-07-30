"""
MCP (Model Context Protocol) configuration for the MCP module.
This file contains all MCP-related settings including server endpoints,
tool routing, and connection parameters.
"""

from typing import Dict, List, Any, Optional
from enum import Enum
from dataclasses import dataclass
from config.settings import settings

class MCPServerType(Enum):
    """Types of MCP servers in the system"""
    MAIN_CYBERSEC = "cybersec_tools"
    INCIDENT_TOOLS = "incident_tools"
    PREVENTION_TOOLS = "prevention_tools"
    THREAT_INTEL = "threat_intel"
    COMPLIANCE_TOOLS = "compliance_tools"


@dataclass
class MCPServerConfig:
    """Configuration for an individual MCP server"""
    name: str
    server_type: MCPServerType
    host: str
    port: int
    protocol: str = "http"
    timeout: int = 30
    retry_attempts: int = 3
    retry_delay: float = 1.0
    enabled: bool = True
    health_check_endpoint: str = "/health"
    api_version: str = "v1"
    
    @property
    def url(self) -> str:
        """Get the full server URL"""
        return f"{self.protocol}://{self.host}:{self.port}"
    
    @property
    def health_check_url(self) -> str:
        """Get the health check URL"""
        return f"{self.url}{self.health_check_endpoint}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "name": self.name,
            "server_type": self.server_type.value,
            "url": self.url,
            "host": self.host,
            "port": self.port,
            "protocol": self.protocol,
            "timeout": self.timeout,
            "enabled": self.enabled
        }


# MCP Server Configurations
SERVERS = {
    MCPServerType.MAIN_CYBERSEC: MCPServerConfig(
        name="Main Cybersecurity Tools Server",
        server_type=MCPServerType.MAIN_CYBERSEC,
        host=settings.MCP_HOST,
        port=settings.MCP_PORT,
        protocol="http",
        timeout=30,
        retry_attempts=3,
        enabled=True
    ),
    MCPServerType.INCIDENT_TOOLS: MCPServerConfig(
        name="Incident Response Tools Server",
        server_type=MCPServerType.INCIDENT_TOOLS,
        host=settings.MCP_HOST,
        port=8081,
        protocol="http",
        timeout=45,  # Incident tools might need more time for forensics
        retry_attempts=3,
        enabled=True
    ),
    MCPServerType.PREVENTION_TOOLS: MCPServerConfig(
        name="Prevention Tools Server",
        server_type=MCPServerType.PREVENTION_TOOLS,
        host=settings.MCP_HOST,
        port=8082,
        protocol="http",
        timeout=30,
        retry_attempts=3,
        enabled=True
    ),
    MCPServerType.THREAT_INTEL: MCPServerConfig(
        name="Threat Intelligence Server",
        server_type=MCPServerType.THREAT_INTEL,
        host=settings.MCP_HOST,
        port=8083,
        protocol="http",
        timeout=60,  # Threat intel queries can take time
        retry_attempts=3,
        enabled=True
    ),
    MCPServerType.COMPLIANCE_TOOLS: MCPServerConfig(
        name="Compliance Tools Server",
        server_type=MCPServerType.COMPLIANCE_TOOLS,
        host=settings.MCP_HOST,
        port=8084,
        protocol="http",
        timeout=30,
        retry_attempts=3,
        enabled=True
    ),
}


# Tool Registry - Maps tools to their handling servers
TOOL_REGISTRY = {
    # Incident Response & Forensics Tools
    "analyze_indicators": {
        "server": MCPServerType.INCIDENT_TOOLS,
        "description": "Analyze IoCs for malicious activity",
        "category": "forensics"
    },
    "memory_dump_analysis": {
        "server": MCPServerType.INCIDENT_TOOLS,
        "description": "Analyze memory dumps for artifacts",
        "category": "forensics",
        "timeout_override": 120  # 2 minutes for large dumps
    },
    "timeline_analysis": {
        "server": MCPServerType.INCIDENT_TOOLS,
        "description": "Create forensic timeline of events",
        "category": "forensics"
    },
    "ioc_extraction": {
        "server": MCPServerType.INCIDENT_TOOLS,
        "description": "Extract IoCs from various sources",
        "category": "forensics"
    },
    
    # Prevention & Architecture Tools
    "search_vulnerabilities": {
        "server": MCPServerType.PREVENTION_TOOLS,
        "description": "Search CVE databases",
        "category": "vulnerability_management"
    },
    "scan_configuration": {
        "server": MCPServerType.PREVENTION_TOOLS,
        "description": "Analyze security configurations",
        "category": "vulnerability_management"
    },
    "security_benchmarks": {
        "server": MCPServerType.PREVENTION_TOOLS,
        "description": "Access security benchmarks and hardening guides",
        "category": "prevention"
    },
    
    # Threat Intelligence Tools
    "threat_feed_search": {
        "server": MCPServerType.THREAT_INTEL,
        "description": "Search threat intelligence feeds",
        "category": "threat_intelligence",
        "timeout_override": 60
    },
    "attribution_lookup": {
        "server": MCPServerType.THREAT_INTEL,
        "description": "Look up threat actor attribution",
        "category": "threat_intelligence"
    },
    "mitre_attack_search": {
        "server": MCPServerType.THREAT_INTEL,
        "description": "Search MITRE ATT&CK framework",
        "category": "threat_intelligence"
    },
    
    # Compliance & GRC Tools
    "compliance_check": {
        "server": MCPServerType.COMPLIANCE_TOOLS,
        "description": "Check compliance against frameworks",
        "category": "compliance",
        "timeout_override": 45
    },
    "regulation_lookup": {
        "server": MCPServerType.COMPLIANCE_TOOLS,
        "description": "Look up regulatory requirements",
        "category": "compliance"
    },
    "breach_calculator": {
        "server": MCPServerType.COMPLIANCE_TOOLS,
        "description": "Calculate breach notification requirements",
        "category": "compliance"
    },
    
    # General Research Tools
    "web_search": {
        "server": MCPServerType.MAIN_CYBERSEC,
        "description": "Search the web for security information",
        "category": "general"
    },
    "knowledge_search": {
        "server": MCPServerType.MAIN_CYBERSEC,
        "description": "Search internal knowledge base",
        "category": "general"
    },
}


# Connection Settings
CONNECTION_CONFIG = {
    "pool": {
        "max_connections": 10,
        "max_keepalive_connections": 5,
        "keepalive_expiry": 600,  # 10 minutes
        "connect_timeout": 5.0,
        "read_timeout": 30.0,
    },
    "retry": {
        "max_attempts": 3,
        "base_delay": 1.0,
        "max_delay": 10.0,
        "exponential_base": 2,
        "retry_on_status_codes": [502, 503, 504],
    },
    "health_check": {
        "interval": 30,  # seconds
        "timeout": 5,
        "failure_threshold": 3,
        "success_threshold": 1,
    }
}


# Tool Categories (for organization and permissions)
CATEGORIES = {
    "forensics": {
        "name": "Digital Forensics",
        "description": "Memory, disk, and network forensics tools"
    },
    "threat_intelligence": {
        "name": "Threat Intelligence", 
        "description": "Threat actor and campaign analysis tools"
    },
    "vulnerability_management": {
        "name": "Vulnerability Management",
        "description": "Vulnerability scanning and patch management"
    },
    "compliance": {
        "name": "Compliance & GRC",
        "description": "Regulatory compliance and governance tools"
    },
    "general": {
        "name": "General Research",
        "description": "Web search and knowledge base tools"
    }
}


# Quick access functions
def get_server(server_type: MCPServerType) -> Optional[MCPServerConfig]:
    """Get server configuration"""
    return SERVERS.get(server_type)


def get_tool_info(tool_name: str) -> Optional[Dict[str, Any]]:
    """Get complete information about a tool"""
    return TOOL_REGISTRY.get(tool_name)


def get_tool_server(tool_name: str) -> Optional[MCPServerType]:
    """Get the server that handles a specific tool"""
    tool_info = get_tool_info(tool_name)
    return tool_info["server"] if tool_info else None


def get_tool_timeout(tool_name: str) -> int:
    """Get timeout for a specific tool"""
    tool_info = get_tool_info(tool_name)
    if tool_info and "timeout_override" in tool_info:
        return tool_info["timeout_override"]
    
    # Get server default timeout
    server_type = get_tool_server(tool_name)
    if server_type:
        server = get_server(server_type)
        return server.timeout if server else 30
    
    return 30  # Default fallback


def get_tools_by_category(category: str) -> List[str]:
    """Get all tools in a specific category"""
    return [
        name for name, info in TOOL_REGISTRY.items()
        if info.get("category") == category
    ]


def get_tools_by_server(server_type: MCPServerType) -> List[str]:
    """Get all tools handled by a specific server"""
    return [
        name for name, info in TOOL_REGISTRY.items()
        if info.get("server") == server_type
    ]


def get_enabled_servers() -> List[MCPServerConfig]:
    """Get list of enabled servers"""
    return [
        server for server in SERVERS.values()
        if server.enabled
    ]


def validate_config() -> Dict[str, Any]:
    """Validate MCP configuration"""
    issues = []
    
    # Check for port conflicts
    ports = [s.port for s in SERVERS.values()]
    if len(ports) != len(set(ports)):
        issues.append("Duplicate ports in server configuration")
    
    # Check all tools have valid servers
    for tool, info in TOOL_REGISTRY.items():
        if info["server"] not in SERVERS:
            issues.append(f"Tool '{tool}' references unknown server")
    
    # Check categories are valid
    for tool, info in TOOL_REGISTRY.items():
        if info.get("category") not in CATEGORIES:
            issues.append(f"Tool '{tool}' has invalid category")
    
    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "stats": {
            "servers": len(SERVERS),
            "enabled_servers": len(get_enabled_servers()),
            "tools": len(TOOL_REGISTRY),
            "categories": len(CATEGORIES)
        }
    }


# Module initialization check
if __name__ == "__main__":
    validation = validate_config()
    print(f"MCP Configuration Status: {'Valid' if validation['valid'] else 'Invalid'}")
    if validation['issues']:
        print("Issues found:")
        for issue in validation['issues']:
            print(f"  - {issue}")
    print(f"\nStatistics: {validation['stats']}")