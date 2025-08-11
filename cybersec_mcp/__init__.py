"""
MCP Package

Model Context Protocol implementation for cybersecurity tools.
Provides unified access to cybersecurity functionality through MCP clients and servers.
"""

# Import main components for easy access with absolute imports
from cybersec_mcp.cybersec_client import CybersecurityMCPClient

# Tools are available through the tools subpackage
from cybersec_mcp import tools

__all__ = [
    'CybersecurityMCPClient',
    'tools'
]
