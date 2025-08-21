"""
Unified Cybersecurity MCP Client

Simple, clean MCP client combining transport and business logic.
Follows the project's patterns for straightforward, maintainable code.
"""

import httpx
import logging
from typing import Dict, Any, Optional, List
from langchain_core.tools import tool

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
    
    def get_langchain_tools(self) -> List:
        """
        Get LangChain tools that wrap the MCP client methods.
        Returns a list of LangChain tools that can be bound to ChatOpenAI.
        """
        # Create tool instances that capture 'self' in their closure
        @tool
        async def web_search_tool(query: str, max_results: int = 5) -> str:
            """Search the web for cybersecurity information and news."""
            try:
                result = await self.search_web(query, max_results)
                # Extract key information and format as string
                if result.get("results"):
                    formatted_results = []
                    for item in result["results"][:max_results]:
                        title = item.get("title", "No title")
                        snippet = item.get("snippet", "No description")
                        url = item.get("url", "")
                        formatted_results.append(f"**{title}**\n{snippet}\nSource: {url}\n")
                    return "\n".join(formatted_results)
                return "No results found for the query."
            except Exception as e:
                return f"Web search failed: {str(e)}"

        @tool
        async def ioc_analysis_tool(indicator: str) -> str:
            """Analyze an Indicator of Compromise (IOC) like IP address, domain, or file hash."""
            try:
                result = await self.analyze_ioc(indicator, "auto")
                # Format the analysis result
                if result.get("analysis"):
                    analysis = result["analysis"]
                    summary = f"IOC Analysis for {indicator}:\n"
                    summary += f"Status: {analysis.get('status', 'Unknown')}\n"
                    if analysis.get("malicious"):
                        summary += "⚠️ MALICIOUS INDICATOR DETECTED\n"
                    summary += f"Details: {analysis.get('details', 'No additional details')}\n"
                    return summary
                return f"Could not analyze indicator: {indicator}"
            except Exception as e:
                return f"IOC analysis failed: {str(e)}"

        @tool  
        async def vulnerability_search_tool(cve_id: str) -> str:
            """Search for details about a CVE (Common Vulnerabilities and Exposures) ID."""
            try:
                result = await self.search_vulnerabilities(cve_id=cve_id)
                # Format vulnerability information
                if result.get("vulnerabilities"):
                    vuln_info = []
                    for vuln in result["vulnerabilities"][:3]:  # Limit to top 3
                        info = f"CVE: {vuln.get('id', 'Unknown')}\n"
                        info += f"Severity: {vuln.get('severity', 'Unknown')}\n"
                        info += f"Score: {vuln.get('score', 'N/A')}\n"
                        info += f"Description: {vuln.get('description', 'No description')}\n"
                        vuln_info.append(info)
                    return "\n---\n".join(vuln_info)
                return f"No vulnerability information found for {cve_id}"
            except Exception as e:
                return f"Vulnerability search failed: {str(e)}"

        @tool
        async def knowledge_search_tool(query: str) -> str:
            """Search the internal knowledge base for company policies, playbooks, and documentation."""
            try:
                result = await self.search_knowledge(query)
                # Format knowledge base results
                if result.get("documents"):
                    docs = []
                    for doc in result["documents"][:3]:  # Limit to top 3
                        title = doc.get("title", "Untitled Document")
                        content = doc.get("content", "No content available")
                        score = doc.get("score", 0)
                        docs.append(f"**{title}** (Relevance: {score:.2f})\n{content[:300]}...")
                    return "\n\n---\n\n".join(docs)
                return "No relevant documents found in knowledge base."
            except Exception as e:
                return f"Knowledge search failed: {str(e)}"

        @tool
        async def attack_surface_analyzer_tool(domain: str) -> str:
            """Analyze a domain's attack surface to identify exposed assets and vulnerabilities."""
            try:
                result = await self.analyze_attack_surface(domain)
                # Format attack surface analysis
                summary = f"Attack Surface Analysis for {domain}:\n"
                if result.get("exposed_services"):
                    summary += f"Exposed Services: {len(result['exposed_services'])}\n"
                    for service in result["exposed_services"][:5]:  # Top 5
                        port = service.get("port", "Unknown")
                        service_name = service.get("service", "Unknown")
                        summary += f"  - Port {port}: {service_name}\n"
                if result.get("vulnerabilities"):
                    summary += f"Potential Vulnerabilities: {len(result['vulnerabilities'])}\n"
                return summary
            except Exception as e:
                return f"Attack surface analysis failed: {str(e)}"

        @tool
        async def threat_feeds_tool(topic: str) -> str:
            """Query threat intelligence feeds for information about threat actors, campaigns, or TTPs."""
            try:
                result = await self.get_threat_feeds(topic, limit=5)
                # Format threat intelligence
                if result.get("feeds"):
                    threats = []
                    for feed in result["feeds"]:
                        title = feed.get("title", "Unknown Threat")
                        description = feed.get("description", "No description")
                        severity = feed.get("severity", "Unknown")
                        threats.append(f"**{title}** (Severity: {severity})\n{description}")
                    return "\n\n---\n\n".join(threats)
                return f"No threat intelligence found for: {topic}"
            except Exception as e:
                return f"Threat feeds query failed: {str(e)}"

        @tool
        async def compliance_guidance_tool(framework: str, query: str) -> str:
            """Get compliance guidance for security frameworks like GDPR, HIPAA, PCI-DSS."""
            try:
                result = await self.get_compliance_guidance(framework, query)
                # Format compliance guidance
                if result.get("guidance"):
                    guidance = result["guidance"]
                    summary = f"Compliance Guidance for {framework}:\n"
                    summary += f"Topic: {query}\n\n"
                    summary += guidance.get("recommendations", "No specific recommendations available.")
                    if guidance.get("requirements"):
                        summary += f"\n\nKey Requirements:\n{guidance['requirements']}"
                    return summary
                return f"No compliance guidance found for {framework} regarding {query}"
            except Exception as e:
                return f"Compliance guidance query failed: {str(e)}"

        # Return all the tools
        return [
            web_search_tool,
            ioc_analysis_tool, 
            vulnerability_search_tool,
            knowledge_search_tool,
            attack_surface_analyzer_tool,
            threat_feeds_tool,
            compliance_guidance_tool
        ]
