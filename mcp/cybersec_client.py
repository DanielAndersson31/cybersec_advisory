"""
Unified Cybersecurity MCP Client

Simple, clean MCP client combining transport and business logic.
Follows the project's patterns for straightforward, maintainable code.
"""

import httpx
import logging
from typing import Dict, Any, Optional

from mcp.config import config

logger = logging.getLogger(__name__)


class MCPClientError(Exception):
    """Base exception for MCP client errors"""
    pass


class CybersecurityMCPClient:
    """
    Unified MCP client for cybersecurity tools.
    Combines HTTP transport with cybersecurity-specific methods.
    """
    
    def __init__(self, agent_name: Optional[str] = None):
        """Initialize the MCP client"""
        self.agent_name = agent_name
        self.server_url = config.get_server_url()
        self.timeout = config.client["default_timeout"]
        
        # Simple HTTP client setup
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            limits=httpx.Limits(
                max_connections=config.client["connection_pool"]["max_connections"],
                max_keepalive_connections=config.client["connection_pool"]["max_keepalive"]
            )
        )
        
        logger.info(f"MCP client initialized for agent: {agent_name}")
    
    async def close(self):
        """Close the HTTP client"""
        await self._client.aclose()
        logger.debug("MCP client closed")
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    # Core MCP method
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call an MCP tool with the given arguments"""
        # Check agent permissions
        if not self._check_permissions(tool_name):
            raise MCPClientError(f"Agent '{self.agent_name}' not authorized for tool '{tool_name}'")
        
        # Prepare request
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        
        headers = {"Content-Type": "application/json"}
        if self.agent_name:
            headers["X-MCP-Agent"] = self.agent_name
        
        try:
            response = await self._client.post(
                f"{self.server_url}/call_tool",
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            
            result = response.json()
            if "error" in result:
                raise MCPClientError(f"Tool error: {result['error']['message']}")
            
            return result.get("result", {})
            
        except httpx.HTTPError as e:
            logger.error(f"MCP tool call failed: {tool_name} - {e}")
            raise MCPClientError(f"Tool call failed: {e}")
    
    def _check_permissions(self, tool_name: str) -> bool:
        """Check if agent can use this tool"""
        agent_permissions = config.get_agent_permissions(self.agent_name)
        if not agent_permissions:
            return False
        
        allowed_tools = agent_permissions.get("allowed_tools", [])
        return tool_name in allowed_tools or "*" in allowed_tools
    
    # Cybersecurity-specific convenience methods
    async def search_web(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """Search web for cybersecurity information"""
        return await self.call_tool("web_search", {
            "query": query,
            "max_results": max_results
        })
    
    async def analyze_ioc(self, indicator: str, indicator_type: str) -> Dict[str, Any]:
        """Analyze an indicator of compromise"""
        return await self.call_tool("ioc_analysis", {
            "indicator": indicator,
            "type": indicator_type
        })
    
    async def search_vulnerabilities(self, cve_id: str = None, keywords: str = None) -> Dict[str, Any]:
        """Search for vulnerability information"""
        args = {}
        if cve_id:
            args["cve_id"] = cve_id
        if keywords:
            args["keywords"] = keywords
        
        return await self.call_tool("vulnerability_search", args)
    
    async def get_threat_feeds(self, feed_type: str = "all") -> Dict[str, Any]:
        """Get latest threat intelligence feeds"""
        return await self.call_tool("threat_feeds", {
            "feed_type": feed_type
        })
    
    async def analyze_attack_surface(self, target: str, scan_type: str = "basic") -> Dict[str, Any]:
        """Analyze attack surface of a target"""
        return await self.call_tool("attack_surface_analyzer", {
            "target": target,
            "scan_type": scan_type
        })
    
    async def monitor_breaches(self, domain: str = None, keywords: str = None) -> Dict[str, Any]:
        """Monitor for data breaches"""
        args = {}
        if domain:
            args["domain"] = domain
        if keywords:
            args["keywords"] = keywords
        
        return await self.call_tool("breach_monitoring", args)
    
    async def get_compliance_guidance(self, framework: str, topic: str = None) -> Dict[str, Any]:
        """Get compliance guidance for security frameworks"""
        args = {"framework": framework}
        if topic:
            args["topic"] = topic
        
        return await self.call_tool("compliance_guidance", args)
    
    async def search_knowledge(self, query: str, domain: str = "cybersecurity") -> Dict[str, Any]:
        """Search the cybersecurity knowledge base"""
        return await self.call_tool("knowledge_search", {
            "query": query,
            "domain": domain
        })