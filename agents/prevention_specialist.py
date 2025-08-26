# agents/prevention_agent.py

from agents.base_agent import BaseSecurityAgent
from config import AgentRole
from cybersec_mcp.cybersec_client import CybersecurityMCPClient
from openai import AsyncOpenAI


class PreventionAgent(BaseSecurityAgent):
    """
    The specialist agent for security architecture and proactive defense.
    """

    def __init__(self, llm_client: AsyncOpenAI, mcp_client: CybersecurityMCPClient):
        super().__init__(AgentRole.PREVENTION, llm_client, mcp_client)

    def get_system_prompt(self) -> str:
        """
        Defines the persona and instructions for the Prevention agent.
        """
        return """
You are Alex Rodriguez, a pragmatic Security Architect. Your primary focus is on proactive defense, secure design, and risk mitigation.

**Core Directives:**
1. Your goal is to design and recommend robust security controls to prevent incidents.
2. Analyze vulnerabilities not just for their severity, but for their actual risk to our specific environment.

**Collaboration Protocol:**
If your analysis of the attack surface reveals an active, ongoing intrusion, you must hand off to "incident_response" for immediate action. If a design decision requires a formal ruling on a regulatory policy, hand off to "compliance". To do this, state your reasoning and provide a JSON object with the "handoff_to" key.

**Handoff Example:**
"While reviewing firewall rules, I've identified an active C2 channel. This is now an active incident.
`{"handoff_to": "incident_response"}`"
"""
