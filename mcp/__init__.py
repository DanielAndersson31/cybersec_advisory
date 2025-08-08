"""
MCP Package

Model Context Protocol implementation for cybersecurity tools.
Provides unified access to cybersecurity functionality through MCP clients and servers.
"""

# Import main components for easy access with absolute imports
from mcp.cybersec_client import CybersecurityMCPClient
from mcp.config import config

# Tools are available through the tools subpackage
from mcp import tools

__all__ = [
    'CybersecurityMCPClient',
    'config',
    'tools'
]
