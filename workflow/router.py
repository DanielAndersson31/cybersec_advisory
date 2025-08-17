"""
Query router for determining which agents should handle a query.
Simple keyword-based routing with expertise matching.
"""

import logging
from typing import List
import instructor
from openai import AsyncOpenAI
from pydantic import ValidationError

from config.agent_config import AgentRole, INTERACTION_RULES
from config.settings import settings
from .schemas import RoutingDecision

logger = logging.getLogger(__name__)


class QueryRouter:
    """
    Routes queries to appropriate cybersecurity agents using a semantic, LLM-based approach.
    """
    
    def __init__(self):
        """Initialize the router with an instructor-patched LLM client."""
        self.llm = instructor.patch(
            AsyncOpenAI(api_key=settings.get_secret("openai_api_key"))
        )
        self.agent_expertise = {
            AgentRole.INCIDENT_RESPONSE: "Handles active security incidents, breaches, malware infections, and suspicious activities. Focuses on containment, eradication, and recovery.",
            AgentRole.PREVENTION: "Focuses on proactive defense, secure architecture, vulnerability management, and risk mitigation. Designs and recommends security controls.",
            AgentRole.THREAT_INTEL: "Analyzes threat actors, their tactics (TTPs), and campaigns. Provides deep, contextualized intelligence on adversary motives and likely future actions.",
            AgentRole.COMPLIANCE: "Specializes in regulatory frameworks (GDPR, HIPAA, PCI-DSS), policies, and audits. Provides guidance on governance and compliance obligations."
        }

    async def determine_relevant_agents(self, query: str) -> List[AgentRole]:
        """
        Determines which agents should respond to a query using an LLM for semantic routing.
        """
        prompt = self._build_routing_prompt(query)
        
        try:
            decision = await self.llm.chat.completions.create(
                model=settings.routing_model_name,
                messages=[{"role": "user", "content": prompt}],
                response_model=RoutingDecision,
                max_retries=2,
            )
            logger.info(f"Routing decision for query '{query[:50]}...': {decision.reasoning}")
            
            # Filter out any roles that are not actual agents
            valid_agents = [role for role in decision.relevant_agents if role in self.agent_expertise]
            return valid_agents
        
        except (ValidationError, Exception) as e:
            logger.error(f"LLM-based routing failed: {e}")
            # Fallback to a safe default if routing fails
            return [AgentRole.INCIDENT_RESPONSE]

    def _build_routing_prompt(self, query: str) -> str:
        """Constructs the prompt for the LLM router."""
        expertise_descriptions = "\\n".join(
            f"- **{role.value}**: {desc}" for role, desc in self.agent_expertise.items()
        )
        
        return f"""
You are an expert request router for a team of cybersecurity specialist agents. Your task is to determine which agent(s) are best suited to handle a given user query based on their described expertise.

**Agent Expertise:**
{expertise_descriptions}

**User Query:**
"{query}"

---
**Instructions:**
1.  Analyze the user's query to understand its intent.
2.  Based on the agent expertise, identify the most appropriate agent(s) to handle the query.
3.  You can select one or more agents. If the query is complex and requires multiple perspectives, select all relevant agents.
4.  Provide a brief reasoning for your choice.
5.  Return your decision in the required structured format. If no specific expertise matches, you may return an empty list.
"""

    def get_primary_agent(self, agents: List[AgentRole]) -> AgentRole:
        """
        Determines the primary agent from a list of relevant agents.
        Uses the speaking order from config.
        """
        if not agents:
            # If the LLM router returns no relevant agents, default to a generalist.
            # Incident Response is often a safe default for unknown security queries.
            logger.warning("No relevant agents identified by router. Defaulting to Incident Response.")
            return AgentRole.INCIDENT_RESPONSE
        
        speaking_order = INTERACTION_RULES.get("speaking_order", [])
        
        for role in speaking_order:
            if role in agents:
                return role
        
        return agents[0]