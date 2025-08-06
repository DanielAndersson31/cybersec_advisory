"""
Base Security Agent

Simple, clean foundation for cybersecurity agents that uses existing agent configuration.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from agents.config import AgentRole, get_agent_config, get_agent_tools
from mcp.cybersec_client import CybersecurityMCPClient

logger = logging.getLogger(__name__)


class BaseSecurityAgent(ABC):
    """
    Base class for all cybersecurity agents.
    Uses the existing agent configuration and provides MCP integration.
    """
    
    def __init__(self, role: AgentRole):
        """
        Initialize the base security agent using existing config.
        
        Args:
            role: The agent's role from AgentRole enum
        """
        # Get configuration from agents/config.py
        self.config = get_agent_config(role)
        self.role = role
        self.name = self.config["name"]
        self.allowed_tools = get_agent_tools(role)
        
        # Initialize MCP client for this agent
        self.mcp_client = CybersecurityMCPClient(agent_name=self.name)
        
        logger.info(f"Initialized {self.name} agent with role {role.value}")
    
    async def process_request(self, request: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process a user request.
        
        Args:
            request: The user's request
            context: Optional context information
            
        Returns:
            Agent's response
        """
        try:
            # Use MCP client to call tools if needed
            # Let the concrete agent handle the actual processing
            return await self._handle_request(request, context or {})
            
        except Exception as e:
            logger.error(f"{self.name} failed to process request: {e}")
            return {
                "success": False,
                "error": str(e),
                "agent": self.name
            }
    
    async def use_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """
        Use an MCP tool if the agent has permission.
        
        Args:
            tool_name: Name of the tool to use
            **kwargs: Tool arguments
            
        Returns:
            Tool execution result
        """
        if tool_name not in self.allowed_tools:
            return {
                "success": False,
                "error": f"Agent {self.name} not authorized to use tool {tool_name}"
            }
        
        try:
            return await self.mcp_client.call_tool(tool_name, kwargs)
        except Exception as e:
            logger.error(f"Tool {tool_name} failed: {e}")
            return {"success": False, "error": str(e)}
    
    @abstractmethod
    async def _handle_request(self, request: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the actual request processing. Must be implemented by subclasses.
        
        Args:
            request: User request
            context: Request context
            
        Returns:
            Agent response
        """
        pass
    
    def __str__(self) -> str:
        return f"{self.name} ({self.role.value})"
