"""
Unified Cybersecurity MCP Client

Simple, clean MCP client combining transport and business logic.
Follows the project's patterns for straightforward, maintainable code.
"""

import httpx
import logging
from typing import Dict, Any, Optional

from config.settings import settings

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
        self.server_url = f"http://{settings.mcp_server_host}:{settings.mcp_server_port}/cybersec_mcp"
        self.timeout = 30.0 # Default timeout
        
        # Simple HTTP client setup
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            limits=httpx.Limits(
                max_connections=10,
                max_keepalive_connections=5
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
        # NOTE: Permissions check is removed as it's a complex feature
        # that was part of the deleted config. Re-implement if needed.
        
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
    
    # Permissions check is disabled as it's no longer configured
    def _check_permissions(self, tool_name: str) -> bool:
        """Permissions are currently disabled."""
        return True
    
    # Cybersecurity-specific convenience methods
    async def search_web(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """Search web for cybersecurity information"""
        # SERVER TOOL: search_web(query, max_results, search_type, include_domains, time_range)
        return await self.call_tool("search_web", {
            
            "query": query,
            "max_results": max_results
        })
    
    async def analyze_ioc(self, indicator: str, indicator_type: str) -> Dict[str, Any]:
        """Analyze an indicator of compromise"""
        # SERVER TOOL: analyze_ioc(indicators: List[str], ...)
        # NOTE: indicator_type is ignored as the server tool does not use it.
        return await self.call_tool("analyze_ioc", {
            "indicators": [indicator], # Server expects a list
        })
    
    async def search_vulnerabilities(self, cve_id: str = None, keywords: str = None) -> Dict[str, Any]:
        """Search for vulnerability information"""
        # SERVER TOOL: find_vulnerabilities(query: str, ...)
        # Use cve_id as the primary query if available, otherwise use keywords.
        query = cve_id if cve_id else keywords
        return await self.call_tool("find_vulnerabilities", {"query": query})
    
    async def get_threat_feeds(
        self, 
        query: str, 
        limit: int = 10, 
        fetch_full_details: bool = False
    ) -> Dict[str, Any]:
        """Get latest threat intelligence feeds"""
        return await self.call_tool("get_threat_feeds", {
            "query": query,
            "limit": limit,
            "fetch_full_details": fetch_full_details,
        })
    
    async def analyze_attack_surface(self, target: str, scan_type: str = "basic") -> Dict[str, Any]:
        """Analyze attack surface of a target"""
        # SERVER TOOL: scan_attack_surface(host: str)
        # NOTE: scan_type is ignored as the server tool does not use it.
        return await self.call_tool("scan_attack_surface", {
            "host": target,
        })
    
    async def check_exposure(self, email_or_domain: str) -> Dict[str, Any]:
        """Check for email or domain exposure."""
        # SERVER TOOL: exposure_checker_tool(email: str)
        return await self.call_tool("exposure_checker_tool", {"email": email_or_domain})

    async def get_compliance_guidance(self, framework: str, topic: str = None) -> Dict[str, Any]:
        """Get compliance guidance for security frameworks"""
        # SERVER TOOL: compliance_guidance(framework, data_type, region, incident_type)
        return await self.call_tool("compliance_guidance", {
            "framework": framework,
            "incident_type": topic, # Map topic to incident_type
        })
    
    async def search_knowledge(self, query: str, domain: str = "cybersecurity") -> Dict[str, Any]:
        """Search the cybersecurity knowledge base"""
        # SERVER TOOL: search_knowledge_base(query, domain, limit, min_score)
        return await self.call_tool("search_knowledge_base", {
            "query": query,
            "domain": domain
        })
