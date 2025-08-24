"""
Simplified Cybersecurity Toolkit
Direct tool implementations without HTTP overhead - Production-ready approach.
"""

import logging
from typing import List, Dict, Any, Optional
from langchain_core.tools import tool
from openai import AsyncOpenAI
from tavily import AsyncTavilyClient

from config.settings import settings
from cybersec_mcp.tools.web_search import WebSearchTool
from cybersec_mcp.tools import (
    knowledge_search,
    analyze_indicators,
    search_vulnerabilities,
    analyze_attack_surface,
    search_threat_feeds,
    get_compliance_guidance,
    check_exposure
)

logger = logging.getLogger(__name__)


class CybersecurityToolkit:
    """
    Simplified cybersecurity toolkit with direct tool access.
    Production-ready approach: No HTTP overhead, direct function calls.
    """
    
    def __init__(self):
        """Initialize toolkit with required API clients"""
        # Initialize shared clients once
        self.llm_client = AsyncOpenAI(api_key=settings.get_secret("openai_api_key"))
        self.web_search_tool_instance = WebSearchTool(llm_client=self.llm_client)
        
        logger.info("CybersecurityToolkit initialized with direct tool access")
    
    # =============================================================================
    # WEB SEARCH TOOLS
    # =============================================================================
    
    async def search_web(self, query: str, max_results: int = 10) -> str:
        """Search the web with LLM-enhanced query optimization for better results."""
        try:
            result = await self.web_search_tool_instance.search(
                query=query,
                max_results=max_results
            )
            
            # Format results for LLM consumption
            if result.results:
                formatted_results = []
                for item in result.results[:max_results]:
                    title = item.title or "No title"
                    content = item.content or "No description"
                    url = item.url or ""
                    formatted_results.append(f"**{title}**\n{content}\nSource: {url}\n")
                return "\n".join(formatted_results)
            return "No results found for the query."
            
        except Exception as e:
            logger.error(f"Web search failed for query '{query}': {e}")
            return f"Web search failed: {str(e)}"
    
    # =============================================================================
    # THREAT INTELLIGENCE TOOLS  
    # =============================================================================
    
    async def analyze_ioc(self, indicator: str) -> str:
        """Analyze an Indicator of Compromise (IOC) like IP address, domain, or file hash."""
        try:
            result = await analyze_indicators(
                indicators=[indicator],
                check_reputation=True,
                enrich_data=True,
                include_context=True
            )
            
            # Format the analysis result
            if result.get("status") == "success" and result.get("results"):
                analysis = result["results"][0]  # First result
                summary = f"IOC Analysis for {indicator}:\n"
                summary += f"Classification: {analysis.get('classification', 'Unknown')}\n"
                
                if analysis.get("classification") == "malicious":
                    summary += "⚠️ MALICIOUS INDICATOR DETECTED\n"
                
                summary += f"Reputation Score: {analysis.get('reputation_score', 'N/A')}\n"
                summary += f"Details: {analysis.get('context', 'No additional details')}\n"
                
                # Add threat intelligence if available
                if analysis.get("threat_intel"):
                    summary += f"Threat Intel: {analysis['threat_intel']}\n"
                
                return summary
            
            return f"Could not analyze indicator: {indicator}"
            
        except Exception as e:
            logger.error(f"IOC analysis failed for {indicator}: {e}")
            return f"IOC analysis failed: {str(e)}"
    
    async def get_threat_feeds(self, topic: str, limit: int = 5) -> str:
        """Query threat intelligence feeds for information about threat actors, campaigns, or TTPs."""
        try:
            result = await search_threat_feeds(
                query=topic,
                limit=limit,
                fetch_full_details=False
            )
            
            # Format threat intelligence
            if result.get("status") == "success" and result.get("results"):
                threats = []
                for feed in result["results"]:
                    title = feed.get("title", "Unknown Threat")
                    description = feed.get("description", "No description")
                    severity = feed.get("severity", "Unknown")
                    threats.append(f"**{title}** (Severity: {severity})\n{description}")
                return "\n\n---\n\n".join(threats)
            
            return f"No threat intelligence found for: {topic}"
            
        except Exception as e:
            logger.error(f"Threat feeds query failed for '{topic}': {e}")
            return f"Threat feeds query failed: {str(e)}"
    
    # =============================================================================
    # VULNERABILITY TOOLS
    # =============================================================================
    
    async def find_vulnerabilities(self, query: str, limit: int = 10) -> str:
        """Search for vulnerabilities by CVE ID, product name, or technology."""
        try:
            result = await search_vulnerabilities(
                query=query,
                severity_filter=None,
                date_range=None,
                product_filter=None,
                include_patched=True,
                limit=limit
            )
            
            # Format vulnerability information
            if result.get("status") == "success" and result.get("results"):
                vuln_info = []
                for vuln in result["results"][:limit]:
                    info = f"CVE: {vuln.get('id', 'Unknown')}\n"
                    info += f"Severity: {vuln.get('severity', 'Unknown')}\n"
                    info += f"Score: {vuln.get('cvss_score', 'N/A')}\n"
                    info += f"Description: {vuln.get('description', 'No description')}\n"
                    
                    if vuln.get("affected_products"):
                        info += f"Affected: {', '.join(vuln['affected_products'][:3])}\n"
                    
                    vuln_info.append(info)
                
                return "\n---\n".join(vuln_info)
            
            return f"No vulnerability information found for {query}"
            
        except Exception as e:
            logger.error(f"Vulnerability search failed for '{query}': {e}")
            return f"Vulnerability search failed: {str(e)}"
    
    # =============================================================================
    # ATTACK SURFACE TOOLS
    # =============================================================================
    
    async def scan_attack_surface(self, target: str) -> str:
        """Analyze the attack surface of a domain or IP address."""
        try:
            result = await analyze_attack_surface(host=target)
            
            # Format attack surface analysis
            if result.get("status") == "success":
                summary = f"Attack Surface Analysis for {target}:\n"
                summary += f"IP Address: {result.get('ip_address', 'Unknown')}\n"
                summary += f"Organization: {result.get('organization', 'Unknown')}\n"
                summary += f"Country: {result.get('country', 'Unknown')}\n"
                
                open_ports = result.get("open_ports", [])
                if open_ports:
                    summary += f"\nOpen Ports ({len(open_ports)}):\n"
                    for port_info in open_ports[:10]:  # Top 10 ports
                        port = port_info.get("port", "Unknown")
                        service = port_info.get("service", "Unknown")
                        summary += f"  - Port {port}: {service}\n"
                else:
                    summary += "\nNo open ports detected\n"
                
                return summary
            
            return f"Could not analyze attack surface for: {target}"
            
        except Exception as e:
            logger.error(f"Attack surface analysis failed for {target}: {e}")
            return f"Attack surface analysis failed: {str(e)}"
    
    # =============================================================================
    # COMPLIANCE TOOLS
    # =============================================================================
    
    async def get_compliance_guidance(self, framework: str, topic: str = None) -> str:
        """Get compliance guidance for security frameworks like GDPR, HIPAA, PCI-DSS."""
        try:
            result = get_compliance_guidance(
                framework=framework,
                data_type=None,
                region=None,
                incident_type=topic
            )
            
            # Format compliance guidance
            if isinstance(result, dict) and result.get("recommendations"):
                summary = f"Compliance Guidance for {framework}:\n"
                if topic:
                    summary += f"Topic: {topic}\n\n"
                
                recommendations = result["recommendations"]
                if isinstance(recommendations, list):
                    for i, rec in enumerate(recommendations[:5], 1):
                        summary += f"{i}. {rec}\n"
                else:
                    summary += f"{recommendations}\n"
                
                if result.get("requirements"):
                    summary += f"\nKey Requirements:\n{result['requirements']}\n"
                
                return summary
            
            return f"No compliance guidance found for {framework}"
            
        except Exception as e:
            logger.error(f"Compliance guidance failed for {framework}: {e}")
            return f"Compliance guidance query failed: {str(e)}"
    
    # =============================================================================
    # KNOWLEDGE BASE TOOLS
    # =============================================================================
    
    async def search_knowledge_base(self, query: str, domain: str = "cybersecurity") -> str:
        """Search the internal knowledge base for company policies, playbooks, and documentation."""
        try:
            result = await knowledge_search(
                query=query,
                domain=domain,
                limit=5
            )
            
            # Format knowledge base results
            if result.get("status") == "success" and result.get("results"):
                docs = []
                for doc in result["results"]:
                    title = doc.get("title", "Untitled Document")
                    content = doc.get("content", "No content available")
                    score = doc.get("score", 0)
                    docs.append(f"**{title}** (Relevance: {score:.2f})\n{content[:300]}...")
                return "\n\n---\n\n".join(docs)
            
            return "No relevant documents found in knowledge base."
            
        except Exception as e:
            logger.error(f"Knowledge search failed for '{query}': {e}")
            return f"Knowledge search failed: {str(e)}"
    
    # =============================================================================
    # EXPOSURE CHECKING TOOLS
    # =============================================================================
    
    async def check_data_exposure(self, email: str) -> str:
        """Check if an email address has been exposed in data breaches."""
        try:
            result = await check_exposure(email=email)
            
            # Format exposure check results
            if result.get("status") == "success":
                if result.get("exposed"):
                    breach_count = result.get("breach_count", 0)
                    breaches = result.get("breaches", [])
                    
                    summary = f"⚠️ EXPOSURE DETECTED for {email}\n"
                    summary += f"Found in {breach_count} breach(es)\n\n"
                    
                    if breaches:
                        summary += "Recent breaches:\n"
                        for breach in breaches[:5]:
                            name = breach.get("name", "Unknown")
                            date = breach.get("date", "Unknown date")
                            summary += f"- {name} ({date})\n"
                    
                    return summary
                else:
                    return f"✅ No data breaches found for {email}"
            
            return f"Could not check exposure for: {email}"
            
        except Exception as e:
            logger.error(f"Exposure check failed for {email}: {e}")
            return f"Exposure check failed: {str(e)}"
    
    # =============================================================================
    # TOOLKIT MANAGEMENT
    # =============================================================================
    
    def get_all_tools(self) -> List:
        """Get all available cybersecurity tools as LangChain StructuredTools"""
        from langchain_core.tools import tool
        
        # Create tool wrappers that properly bind to this instance
        @tool
        async def search_web(query: str, max_results: int = 10) -> str:
            """Search the web with LLM-enhanced query optimization for better results."""
            return await self.search_web(query, max_results)
        
        @tool
        async def analyze_ioc(indicator: str) -> str:
            """Analyze an Indicator of Compromise (IOC) like IP address, domain, or file hash."""
            return await self.analyze_ioc(indicator)
        
        @tool
        async def get_threat_feeds(topic: str, limit: int = 5) -> str:
            """Query threat intelligence feeds for information about threat actors, campaigns, or TTPs."""
            return await self.get_threat_feeds(topic, limit)
        
        @tool
        async def find_vulnerabilities(query: str, limit: int = 10) -> str:
            """Search for vulnerabilities by CVE ID, product name, or technology."""
            return await self.find_vulnerabilities(query, limit)
        
        @tool
        async def scan_attack_surface(target: str) -> str:
            """Analyze the attack surface of a domain or IP address."""
            return await self.scan_attack_surface(target)
        
        @tool
        async def get_compliance_guidance(framework: str, topic: str = None) -> str:
            """Get compliance guidance for security frameworks like GDPR, HIPAA, PCI-DSS."""
            return await self.get_compliance_guidance(framework, topic)
        
        @tool
        async def search_knowledge_base(query: str, domain: str = "cybersecurity") -> str:
            """Search the internal knowledge base for company policies, playbooks, and documentation."""
            return await self.search_knowledge_base(query, domain)
        
        @tool
        async def check_data_exposure(email: str) -> str:
            """Check if an email address has been exposed in data breaches."""
            return await self.check_data_exposure(email)
        
        return [
            search_web,
            analyze_ioc,
            get_threat_feeds,
            find_vulnerabilities,
            scan_attack_surface,
            get_compliance_guidance,
            search_knowledge_base,
            check_data_exposure,
        ]
    
    def get_tools_by_category(self, category: str) -> List:
        """Get tools filtered by category"""
        all_tools = self.get_all_tools()
        
        # Map tool names to categories
        tool_categories = {
            "general": ["search_web", "search_knowledge_base"],
            "threat_intel": ["analyze_ioc", "get_threat_feeds"],
            "prevention": ["find_vulnerabilities", "scan_attack_surface"],
            "compliance": ["get_compliance_guidance"],
            "incident_response": ["analyze_ioc", "check_data_exposure"],
        }
        
        category_tool_names = tool_categories.get(category, [])
        return [tool for tool in all_tools if tool.name in category_tool_names]


# Global toolkit instance for easy access
cybersec_toolkit = CybersecurityToolkit()
