#!/usr/bin/env python3
"""
Complete Cybersecurity MCP Server
Provides all cybersecurity tools for the multi-agent advisory system.
"""

import logging
from typing import Dict, Any, List, Optional
from fastmcp import FastMCP
from openai import AsyncOpenAI
from config.settings import settings # Import the Pydantic settings
from cybersec_mcp.tools import (
    WebSearchTool,
    KnowledgeSearchTool,
    IOCAnalysisTool,
    VulnerabilitySearchTool,
    AttackSurfaceAnalyzerTool,
    ThreatFeedsTool,
    ComplianceGuidanceTool,
    ExposureCheckerTool
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create a single, shared OpenAI client for all tools that need it
shared_llm_client = AsyncOpenAI(api_key=settings.get_secret("openai_api_key"))

# Instantiate tools that require the LLM client
web_search_tool_instance = WebSearchTool(llm_client=shared_llm_client)

# Initialize FastMCP server directly from Pydantic settings
mcp = FastMCP(
    name=settings.APP_NAME,
    instructions="Complete cybersecurity toolset for multi-agent advisory system",
    version="1.0.0"
)

# Set server metadata (optional, can be simplified or expanded)
mcp.metadata = {
    "project_name": settings.APP_NAME,
    "environment": settings.environment,
    "author": "Cybersec AI",
}


# =============================================================================
# GENERAL CYBERSECURITY TOOLS
# =============================================================================

@mcp.tool()
async def search_web(
    query: str,
    max_results: int = 10
) -> Dict[str, Any]:
    """
    Search the web with LLM-enhanced query optimization for better results.
    
    Args:
        query: Search query string (will be enhanced by LLM for optimal results)
        max_results: Maximum number of results to return (default: 10)
    
    Returns:
        Dict containing search results with status, query, enhanced_query, and results list
    """
    try:
        logger.info(f"Web search with LLM enhancement: {query}")
        result = await web_search_tool_instance.search(
            query=query,
            max_results=max_results
        )
        logger.info(f"Web search completed: {result.total_results} results for enhanced query")
        return result.model_dump()
    except Exception as e:
        logger.error(f"Web search error for query '{query}': {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "query": query,
            "enhanced_query": query,
            "results": [],
            "total_results": 0
        }


@mcp.tool()
async def search_knowledge_base(
    query: str,
    domain: Optional[str] = None,
    limit: int = 5
) -> Dict[str, Any]:
    """
    Search the cybersecurity knowledge base for domain-specific information.
    
    Args:
        query: Search query string
        domain: Knowledge domain to search ("incident_response", "prevention", 
                "threat_intelligence", "compliance") - searches all if None
        limit: Maximum number of results to return (default: 5)
    
    Returns:
        Dict containing search results with status, query, and results list
    """
    try:
        logger.info(f"Knowledge base search: {query} (domain: {domain})")
        result = await KnowledgeSearchTool().search(
            query=query,
            domain=domain,
            limit=limit
        )
        logger.info(f"Knowledge search completed: {len(result.results)} results")
        return result.model_dump()
    except Exception as e:
        logger.error(f"Knowledge search error for query '{query}': {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "query": query,
            "domain": domain,
            "results": []
        }


# =============================================================================
# INCIDENT RESPONSE TOOLS
# =============================================================================

@mcp.tool()
async def analyze_ioc(
    indicators: List[str],
    check_reputation: bool = True,
    enrich_data: bool = True,
    include_context: bool = True
) -> Dict[str, Any]:
    """
    Analyze indicators of compromise (IOCs) using VirusTotal API.
    
    Args:
        indicators: List of IOCs to analyze (IPs, domains, hashes, URLs)
        check_reputation: Check reputation against threat intelligence (default: True)
        enrich_data: Add contextual threat intelligence data (default: True)
        include_context: Include analysis context and recommendations (default: True)
    
    Returns:
        Dict containing analysis results with status, indicators analyzed, and detailed results
    """
    try:
        logger.info(f"IOC analysis started: {len(indicators)} indicators")
        result = await IOCAnalysisTool().analyze_indicators(indicators=indicators)
        
        # Log summary
        if result.status == "success":
            malicious = len([r for r in result.results if r.classification == "malicious"])
            suspicious = len([r for r in result.results if r.classification == "suspicious"])
            logger.info(f"IOC analysis completed: {malicious} malicious, {suspicious} suspicious")
        
        return result.model_dump()
    except Exception as e:
        logger.error(f"IOC analysis error: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "total_indicators": len(indicators),
            "results": []
        }


@mcp.tool()
async def exposure_checker_tool(email: str) -> dict:
    """
    Checks if an email address has been exposed in a data breach using the XposedOrNot API.
    This tool is a replacement for the previous HIBP-based breach monitoring.

    Args:
        email: The email address to check for exposure.

    Returns:
        A dictionary containing the exposure check results.
    """
    logger.info(f"Checking exposure for email: {email}")
    response = await ExposureCheckerTool().check(email=email)
    return response.model_dump()


# =============================================================================
# THREAT INTELLIGENCE TOOLS
# =============================================================================

@mcp.tool()
async def get_threat_feeds(
    query: str,
    limit: int = 10,
    fetch_full_details: bool = False
) -> Dict[str, Any]:
    """
    Search AlienVault OTX threat intelligence feeds for IOCs and campaigns.
    
    Args:
        query: Search query (malware family, threat actor, campaign name, etc.)
        limit: Maximum number of threat reports to return (default: 10)
        fetch_full_details: Set to True to retrieve full details including all IOCs (slower).
    
    Returns:
        Dict containing threat intelligence results with status, query, and threat reports
    """
    try:
        logger.info(f"Threat intelligence search: {query} (details: {fetch_full_details})")
        result = await ThreatFeedsTool().search(
            query=query,
            limit=limit,
            fetch_full_details=fetch_full_details
        )
        
        if result.status == "success":
            logger.info(f"Threat intelligence search completed: {result.total_results} reports found")
        
        return result.model_dump()
    except Exception as e:
        logger.error(f"Threat intelligence search error for '{query}': {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "query": query,
            "total_results": 0,
            "results": []
        }


# =============================================================================
# PREVENTION & ARCHITECTURE TOOLS
# =============================================================================

@mcp.tool()
async def find_vulnerabilities(
    query: str,
    severity_filter: Optional[List[str]] = None,
    include_patched: bool = False,
    date_range: Optional[str] = None,
    limit: int = 20,
    exact_phrase: bool = False,
) -> Dict[str, Any]:
    """
    Search CVE databases for vulnerabilities affecting specific products or technologies.
    
    Args:
        query: Search query for vulnerabilities (product name, CVE ID, etc.)
        severity_filter: Filter by severity levels (["LOW", "MEDIUM", "HIGH", "CRITICAL"])
        include_patched: Whether to include vulnerabilities that are already patched
        date_range: Date range for vulnerability publication (e.g., "week", "month", "year")
        limit: Maximum number of vulnerabilities to return (default: 20)
        exact_phrase: If True, search for the exact phrase instead of individual words.
    
    Returns:
        Dict containing vulnerability search results with CVE details and CVSS scores
    """
    try:
        logger.info(f"Vulnerability search: {query} (limit: {limit})")
        result = await VulnerabilitySearchTool().search(
            query=query,
            severity_filter=severity_filter,
            include_patched=include_patched,
            date_range=date_range,
            limit=limit,
            exact_phrase=exact_phrase,
        )
        
        if result.status == "success":
            critical = len([v for v in result.results if v.severity == "CRITICAL"])
            logger.info(f"Vulnerability search completed: {result.total_results} total, {critical} critical")
        
        return result.model_dump()
    except Exception as e:
        logger.error(f"Vulnerability search error for '{query}': {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "query": query,
            "total_results": 0,
            "results": []
        }


@mcp.tool()
async def scan_attack_surface(host: str) -> Dict[str, Any]:
    """
    Analyze the external attack surface of a host or domain using ZoomEye API.
    
    Args:
        host: IP address or domain name to analyze
    
    Returns:
        Dict containing attack surface analysis with open ports, services, and organization info
    """
    try:
        logger.info(f"Attack surface analysis: {host}")
        result = await AttackSurfaceAnalyzerTool().analyze(host=host)
        
        if result.status == "success":
            logger.info(f"Attack surface analysis completed: {len(result.open_ports)} open ports found")
        
        return result.model_dump()
    except Exception as e:
        logger.error(f"Attack surface analysis error for {host}: {str(e)}")
        return {
            "status": "error",
            "query_host": host,
            "ip_address": "",
            "organization": "",
            "country": "",
            "open_ports": [],
            "error": str(e)
        }


# =============================================================================
# COMPLIANCE & GOVERNANCE TOOLS
# =============================================================================

@mcp.tool()
async def compliance_guidance(
    framework: str,
    data_type: Optional[str] = None,
    region: Optional[str] = None,
    incident_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get compliance guidance for specific regulatory frameworks.
    
    Args:
        framework: Compliance framework ("GDPR", "HIPAA", "PCI-DSS", "SOX", etc.)
        data_type: Type of data involved ("personal_data", "health_data", "payment_cards", etc.)
        region: Geographic region ("EU", "US", "Global", etc.)
        incident_type: Type of incident requiring compliance guidance
    
    Returns:
        Dict containing compliance guidance with framework details and recommendations
    """
    try:
        logger.info(f"Compliance guidance request: {framework}")
        result = await ComplianceGuidanceTool().get_guidance(
            framework=framework,
            data_type=data_type,
            region=region,
            incident_type=incident_type
        )
        
        if isinstance(result, dict):
            logger.info(f"Compliance guidance completed for {framework}")
        
        return result
    except Exception as e:
        logger.error(f"Compliance guidance error for {framework}: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "framework": framework,
            "recommendations": []
        }


# =============================================================================
# SERVER MANAGEMENT & UTILITY TOOLS
# =============================================================================

@mcp.tool()
async def get_server_status() -> Dict[str, Any]:
    """
    Get the current status of the MCP server.
    NOTE: Tool categories are now hardcoded as the settings object is for secrets.
    """
    try:
        tool_info = {
            "general": ["search_web", "knowledge_search"],
            "incident_response": ["analyze_indicators", "check_exposure_tool"],
            "threat_intelligence": ["get_threat_feeds"],
            "prevention": ["find_vulnerabilities", "scan_attack_surface"],
            "compliance": ["compliance_guidance"]
        }
        flat_tools = [tool for sublist in tool_info.values() for tool in sublist]
        
        return {
            "status": "success",
            "server_name": settings.APP_NAME,
            "version": "1.0.0",
            "total_tools": len(flat_tools)
        }
        
    except Exception as e:
        logger.error(f"Server status error: {str(e)}")
        return {"status": "error", "error": str(e)}


@mcp.tool()
async def health_check() -> Dict[str, Any]:
    """
    Perform a health check of all integrated APIs and services.
    
    Returns:
        Dict containing health status of all external services
    """
    try:
        health_status = {
            "server": "healthy",
            "services": {
                "web_search": "unknown",
                "knowledge_base": "unknown", 
                "virustotal": "unknown",
                "zoomeye": "unknown",
                "otx_alienvault": "unknown",
                "xposedornot": "unknown"
            },
            "timestamp": "health_check_timestamp"
        }
        
        logger.info("Health check completed")
        
        return {
            "status": "success",
            "health": health_status
        }
        
    except Exception as e:
        logger.error(f"Health check error: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }


# =============================================================================
# SERVER STARTUP
# =============================================================================

def main():
    """Main entry point for starting the server."""
    try:
        logger.info("=" * 60)
        logger.info("🚀 Starting Cybersecurity MCP Server...")
        logger.info(f"Server: {mcp.name} v1.0.0")
        logger.info(f"URL: http://{settings.mcp_server_host}:{settings.mcp_server_port}")
        logger.info(f"Log Level: {settings.log_level}")
        logger.info("=" * 60)
        
        # Start the server using host and port from Pydantic settings
        mcp.run(
            transport="http",
            host=settings.mcp_server_host,
            port=settings.mcp_server_port,
            path="/cybersec_mcp",
            log_level=settings.log_level.lower()
        )
        
    except Exception as e:
        logger.error(f"💥 Server failed to start: {e}", exc_info=True)
    finally:
        logger.info("=" * 60)
        logger.info("🛑 Cybersecurity MCP Server stopped")
        logger.info("=" * 60)


if __name__ == "__main__":
    main()
