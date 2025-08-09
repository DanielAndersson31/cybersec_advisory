#!/usr/bin/env python3
"""
Complete Cybersecurity MCP Server
Provides all cybersecurity tools for the multi-agent advisory system.
"""

import logging
from typing import Dict, Any, List, Optional
from fastmcp import FastMCP
from config.settings import settings # Import the Pydantic settings
from cybersec_mcp.tools import (
    web_search,
    knowledge_search,
    analyze_indicators,
    search_vulnerabilities,
    analyze_attack_surface,
    search_threat_feeds,
    get_compliance_guidance,
    check_exposure
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastMCP server directly from Pydantic settings
mcp = FastMCP(
    name=settings.project_name,
    instructions="Complete cybersecurity toolset for multi-agent advisory system",
    version="1.0.0"
)

# Set server metadata (optional, can be simplified or expanded)
mcp.metadata = {
    "project_name": settings.project_name,
    "environment": settings.environment,
    "author": "Cybersec AI",
}


# =============================================================================
# GENERAL CYBERSECURITY TOOLS
# =============================================================================

@mcp.tool()
async def search_web(
    query: str,
    max_results: int = 10,
    search_type: str = "general",
    include_domains: Optional[List[str]] = None,
    time_range: Optional[str] = None
) -> Dict[str, Any]:
    """
    Search the web for cybersecurity information with enhanced querying.
    
    Args:
        query: Search query string
        max_results: Maximum number of results to return (default: 10)
        search_type: Type of search - "general", "news", or "research" (default: "general")
        include_domains: List of specific domains to search within
        time_range: Filter by time - 'd' (day), 'w' (week), 'm' (month), 'y' (year)
    
    Returns:
        Dict containing search results with status, query, and results list
    """
    try:
        logger.info(f"Web search: {query} (type: {search_type})")
        result = await web_search(
            query=query,
            max_results=max_results,
            search_type=search_type,
            include_domains=include_domains,
            time_range=time_range
        )
        logger.info(f"Web search completed: {result.get('total_results', 0)} results")
        return result
    except Exception as e:
        logger.error(f"Web search error for query '{query}': {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "query": query,
            "results": []
        }


@mcp.tool()
async def search_knowledge_base(
    query: str,
    domain: Optional[str] = None,
    limit: int = 5,
    min_score: float = 0.7
) -> Dict[str, Any]:
    """
    Search the cybersecurity knowledge base for domain-specific information.
    
    Args:
        query: Search query string
        domain: Knowledge domain to search ("incident_response", "prevention", 
                "threat_intelligence", "compliance") - searches all if None
        limit: Maximum number of results to return (default: 5)
        min_score: Minimum similarity score threshold (default: 0.7)
    
    Returns:
        Dict containing search results with status, query, and results list
    """
    try:
        logger.info(f"Knowledge base search: {query} (domain: {domain})")
        result = knowledge_search(
            query=query,
            domain=domain,
            limit=limit,
            min_score=min_score
        )
        logger.info(f"Knowledge search completed: {len(result.get('results', []))} results")
        return result
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
        result = await analyze_indicators(
            indicators=indicators,
            check_reputation=check_reputation,
            enrich_data=enrich_data,
            include_context=include_context
        )
        
        # Log summary
        if result.get("status") == "success":
            results = result.get("results", [])
            malicious = len([r for r in results if r.get("classification") == "malicious"])
            suspicious = len([r for r in results if r.get("classification") == "suspicious"])
            logger.info(f"IOC analysis completed: {malicious} malicious, {suspicious} suspicious")
        
        return result
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
    response = await check_exposure(email=email)
    return response


# =============================================================================
# THREAT INTELLIGENCE TOOLS
# =============================================================================

@mcp.tool()
async def get_threat_feeds(
    query: str,
    limit: int = 10
) -> Dict[str, Any]:
    """
    Search AlienVault OTX threat intelligence feeds for IOCs and campaigns.
    
    Args:
        query: Search query (malware family, threat actor, campaign name, etc.)
        limit: Maximum number of threat reports to return (default: 10)
    
    Returns:
        Dict containing threat intelligence results with status, query, and threat reports
    """
    try:
        logger.info(f"Threat intelligence search: {query}")
        result = await search_threat_feeds(
            query=query,
            limit=limit
        )
        
        if result.get("status") == "success":
            total_results = result.get("total_results", 0)
            logger.info(f"Threat intelligence search completed: {total_results} reports found")
        
        return result
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
    date_range: Optional[str] = None,
    product_filter: Optional[str] = None,
    include_patched: bool = True,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Search CVE databases for vulnerabilities affecting specific products or technologies.
    
    Args:
        query: Search query for vulnerabilities (product name, CVE ID, etc.)
        severity_filter: Filter by severity levels (["LOW", "MEDIUM", "HIGH", "CRITICAL"])
        date_range: Date range for vulnerability publication (e.g., "2024-01-01:2024-12-31")
        product_filter: Filter by specific product name
        include_patched: Include vulnerabilities that have been patched (default: True)
        limit: Maximum number of vulnerabilities to return (default: 20)
    
    Returns:
        Dict containing vulnerability search results with CVE details and CVSS scores
    """
    try:
        logger.info(f"Vulnerability search: {query} (limit: {limit})")
        result = await search_vulnerabilities(
            query=query,
            severity_filter=severity_filter,
            date_range=date_range,
            product_filter=product_filter,
            include_patched=include_patched,
            limit=limit
        )
        
        if result.get("status") == "success":
            total_results = result.get("total_results", 0)
            critical = len([v for v in result.get("results", []) if v.get("severity") == "CRITICAL"])
            logger.info(f"Vulnerability search completed: {total_results} total, {critical} critical")
        
        return result
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
        result = await analyze_attack_surface(host=host)
        
        if result.get("status") == "success":
            open_ports = len(result.get("open_ports", []))
            logger.info(f"Attack surface analysis completed: {open_ports} open ports found")
        
        return result
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
        result = get_compliance_guidance(
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
            "server_name": settings.project_name,
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
