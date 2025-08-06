# mcp/config.py
"""
MCP Server Configuration
Clean and focused configuration management.
"""
from typing import Dict, Any, List
from config.settings import settings


class MCPConfig:
    """
    MCP server configuration with validation.
    Keeps it simple and focused on configuration management.
    """
    
    def __init__(self):
        """Initialize the MCP configuration."""
        self._server_config = {
            "name": "Cybersecurity Tools Server",
            "host": settings.MCP_HOST,
            "port": settings.MCP_PORT,
            "timeout": 60,
            "description": "Complete cybersecurity toolset for multi-agent advisory system",
            "version": "1.0.0",
            "author": "Cybersec AI",
            "contact": "info@cybersecai.com"
        }
        
        self._client_config = {
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
        
        self._tool_categories = {
            "general": [
                "search_web",
                "search_knowledge_base", 
                "get_server_status",
                "health_check"
            ],
            "incident_response": [
                "analyze_indicators",
                "check_breach_exposure"
            ],
            "threat_intelligence": [
                "search_threat_feeds"
            ],
            "prevention": [
                "search_vulnerabilities",
                "analyze_attack_surface"
            ],
            "compliance": [
                "get_compliance_guidance"
            ]
        }
        
        self._agent_permissions = {
            "incident_response_agent": [
                "analyze_indicators",
                "check_breach_exposure",
                "search_knowledge_base",
                "search_web"
            ],
            "threat_intel_agent": [
                "search_threat_feeds",
                "analyze_indicators", 
                "search_knowledge_base",
                "search_web"
            ],
            "prevention_agent": [
                "search_vulnerabilities",
                "analyze_attack_surface",
                "search_knowledge_base",
                "search_web"
            ],
            "compliance_agent": [
                "get_compliance_guidance",
                "check_breach_exposure",
                "search_knowledge_base", 
                "search_web"
            ],
            "coordinator_agent": [
                "search_knowledge_base",
                "search_web",
                "get_server_status",
                "health_check"
            ]
        }

    # Properties for clean access
    @property
    def server(self) -> Dict[str, Any]:
        """Get server configuration."""
        return self._server_config.copy()
    
    @property
    def client(self) -> Dict[str, Any]:
        """Get client configuration."""
        return self._client_config.copy()
    
    @property
    def tool_categories(self) -> Dict[str, List[str]]:
        """Get tool categories."""
        return self._tool_categories.copy()
    
    @property
    def agent_permissions(self) -> Dict[str, List[str]]:
        """Get agent tool permissions."""
        return self._agent_permissions.copy()

    # Essential operations only
    def get_server_url(self) -> str:
        """Get the full server URL."""
        return f"http://{self._server_config['host']}:{self._server_config['port']}"
    
    def get_tools_for_agent(self, agent_name: str) -> List[str]:
        """Get allowed tools for a specific agent."""
        return self._agent_permissions.get(agent_name, []).copy()
    
    def validate(self) -> bool:
        """
        Validate the configuration.
        
        Returns:
            True if valid, False otherwise
        """
        try:
            # Check server essentials
            if not self._server_config.get("host") or not self._server_config.get("port"):
                return False
            
            # Check port range
            if not (1000 <= self._server_config["port"] <= 65535):
                return False
            
            return True
        except Exception:
            return False
    
    def validate_or_raise(self) -> None:
        """Validate configuration and raise exception if invalid."""
        if not self.validate():
            raise ValueError("Invalid MCP configuration")

    def __repr__(self) -> str:
        """String representation."""
        return f"MCPConfig(name='{self._server_config['name']}', port={self._server_config['port']})"


# Global configuration instance
config = MCPConfig()

# Convenience exports for backwards compatibility
MCP_SERVER = config.server
CLIENT_CONFIG = config.client  
TOOL_CATEGORIES = config.tool_categories
AGENT_TOOL_PERMISSIONS = config.agent_permissions