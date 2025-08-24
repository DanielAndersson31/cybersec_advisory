"""
MCP Package

Model Context Protocol implementation for external cybersecurity tool integrations.
For internal tools, use cybersec_tools.py instead.

This package provides:
- ExternalMCPClient: For Claude Desktop and external integrations  
- MCP Server: For exposing tools via MCP protocol
- Individual Tools: For building custom integrations
"""

# Import main components for easy access
from cybersec_mcp.cybersec_client import ExternalMCPClient, CybersecurityMCPClient

# Tools are available through the tools subpackage
from cybersec_mcp import tools

__all__ = [
    'ExternalMCPClient',       # New preferred name
    'CybersecurityMCPClient',  # Backward compatibility
    'tools'
]
