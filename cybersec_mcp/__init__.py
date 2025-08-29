"""
Cybersecurity MCP Package

Direct tool implementation for the cybersecurity advisory system.
Uses efficient in-process tool execution via CybersecurityToolkit.

This package provides:
- CybersecurityToolkit: Main toolkit for direct tool access (production use)
- cybersec_tools_server: MCP server for testing with MCP Inspector
- Individual Tools: Specialized cybersecurity analysis tools
"""

# Import main components for easy access
from cybersec_mcp.cybersec_tools import CybersecurityToolkit

# Tools are available through the tools subpackage
from cybersec_mcp import tools

__all__ = [
    'CybersecurityToolkit',
    'tools'
]
