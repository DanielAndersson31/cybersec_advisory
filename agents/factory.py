# agents/factory.py

import logging
from typing import Dict

from openai import AsyncOpenAI

# Use the centralized config package for all configuration needs.
from config.agent_config import AgentRole, get_enabled_agents
from cybersec_mcp.cybersec_client import CybersecurityMCPClient

# Import the base and all specialist agent classes
from agents.base_agent import BaseSecurityAgent
from agents.incident_responder import IncidentResponseAgent
from agents.threat_analyst import ThreatIntelAgent
from agents.prevention_specialist import PreventionAgent
from agents.compliance_specialist import ComplianceAgent

logger = logging.getLogger(__name__)


class AgentFactory:
    """Dependency injection and agent creation"""

    def __init__(self, llm_client: AsyncOpenAI, mcp_client: CybersecurityMCPClient):
        """Initialize the factory with shared clients."""
        self.llm_client = llm_client
        self.mcp_client = mcp_client
        self.agent_class_map = {
            AgentRole.INCIDENT_RESPONSE: IncidentResponseAgent,
            AgentRole.THREAT_INTEL: ThreatIntelAgent,
            AgentRole.PREVENTION: PreventionAgent,
            AgentRole.COMPLIANCE: ComplianceAgent,
        }

    def create_agent(self, role: AgentRole) -> BaseSecurityAgent:
        """Create a single agent with injected dependencies."""
        if role in self.agent_class_map:
            AgentClass = self.agent_class_map[role]
            try:
                agent_instance = AgentClass(llm_client=self.llm_client, mcp_client=self.mcp_client)
                logger.info(f"Successfully created agent: {agent_instance.name}")
                return agent_instance
            except Exception as e:
                logger.error(f"Failed to create agent for role {role.value}: {e}", exc_info=True)
                raise
        else:
            raise ValueError(f"No agent class found for role: {role.value}")

    def create_all_agents(self) -> Dict[AgentRole, BaseSecurityAgent]:
        """Creates a pool of all enabled specialist agents."""
        logger.info("Creating agent pool...")
        agent_pool: Dict[AgentRole, BaseSecurityAgent] = {}
        enabled_agent_configs = get_enabled_agents()

        for agent_config in enabled_agent_configs:
            role = agent_config["role"]
            if role in self.agent_class_map:
                agent_pool[role] = self.create_agent(role)
            elif role != AgentRole.COORDINATOR:
                logger.warning(f"Skipping disabled or unmapped agent role: {role.value}")

        logger.info(f"Agent pool creation complete with {len(agent_pool)} agents.")
        return agent_pool
