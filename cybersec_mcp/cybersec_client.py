"""
External MCP Client for Cybersecurity Tools

Lightweight MCP client for external integrations (Claude Desktop, etc.).
For internal tool usage, use cybersec_tools.py instead.
"""

import httpx
import logging
from typing import Dict, Any, Optional

from config.settings import settings

logger = logging.getLogger(__name__)


class MCPClientError(Exception):
    """Base exception for MCP client errors"""
    pass


class ExternalMCPClient:
    """
    Lightweight MCP client for external integrations only.
    
    Use Cases:
    - Claude Desktop integration
    - External tool access via MCP protocol
    - Cross-process communication
    
    For internal application tools, use cybersec_tools.py instead.
    """
    
    def __init__(self, agent_name: Optional[str] = None):
        """Initialize the MCP client"""
        self.agent_name = agent_name
        self.server_url = f"http://{settings.mcp_server_host}:{settings.mcp_server_port}/cybersec_mcp/"
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
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }
        if self.agent_name:
            headers["X-MCP-Agent"] = self.agent_name
        
        try:
            response = await self._client.post(
                self.server_url,  # FastMCP serves tools at the base path
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
    
    # For external integrations, use call_tool directly
    # All convenience methods moved to cybersec_tools.py for internal use

    
    # Example usage for external integrations:
    # client = ExternalMCPClient()
    # result = await client.call_tool("search_web", {"query": "threat intel", "max_results": 5})
    
    async def list_available_tools(self) -> Dict[str, Any]:
        """List all tools available on the MCP server"""
        try:
            response = await self._client.post(
                self.server_url,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/list",
                    "params": {}
                },
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream"
                }
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to list tools: {e}")
            return {"error": str(e), "tools": []}


# For backward compatibility
CybersecurityMCPClient = ExternalMCPClient


# Example usage for external integrations:
"""
# Basic tool calling
client = ExternalMCPClient()
result = await client.call_tool("search_web", {
    "query": "latest cybersecurity threats", 
    "max_results": 5
})

# List available tools
tools = await client.list_available_tools()
print("Available tools:", tools)

# Don't forget to close the client
await client.close()

# Or use as context manager
async with ExternalMCPClient() as client:
    result = await client.call_tool("analyze_ioc", {
        "indicators": ["1.2.3.4"]
    })
"""
