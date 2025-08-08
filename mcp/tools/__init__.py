"""
MCP Tools Package

Contains all cybersecurity tools available through the MCP server.
Each tool module provides specific cybersecurity functionality.
"""

# Import all tool functions with absolute imports and correct function names
from mcp.tools.web_search import web_search
from mcp.tools.knowledge_search import knowledge_search
from mcp.tools.ioc_analysis import analyze_indicators
from mcp.tools.vulnerability_search import search_vulnerabilities
from mcp.tools.attack_surface_analyzer import analyze_attack_surface
from mcp.tools.threat_feeds import search_threat_feeds
from mcp.tools.compliance_guidance import get_compliance_guidance
from mcp.tools.breach_monitoring import check_breached_email

# Define what's available when importing from this package
__all__ = [
    'web_search',
    'knowledge_search', 
    'analyze_indicators',
    'search_vulnerabilities',
    'analyze_attack_surface',
    'search_threat_feeds',
    'get_compliance_guidance',
    'check_breached_email'  # Corrected function name
]
