# agents/factory.py

import logging
from typing import Dict

from openai import AsyncOpenAI

# Assuming your config and client are accessible from a parent directory.
# Adjust import paths based on your project's final structure.
from config import AgentRole, get_enabled_agents
from cybersec_mcp.cybersec_client import CybersecurityMCPClient

# Import the base and all specialist agent classes
from .base_agent import BaseSecurityAgent
from agents.incident_responder import IncidentResponseAgent
from agents.threat_analyst import ThreatIntelAgent
from agents.prevention_specialist import PreventionAgent
from agents.compliance_specialist import ComplianceAgent

logger = logging.getLogger(__name__)


def create_agent_pool() -> Dict[AgentRole, BaseSecurityAgent]:
    """
    Initializes clients and creates a pool of all enabled specialist agents.

    This factory handles dependency injection by creating the LLM and tool clients
    once and passing them to each agent upon creation.

    Returns:
        A dictionary mapping each agent's role to its initialized instance.
    """
    logger.info("Creating agent pool...")

    # Initialize the clients that will be shared by all agents
    llm_client = AsyncOpenAI()
    mcp_client = CybersecurityMCPClient()

    # Map the AgentRole enum to the corresponding agent class
    agent_class_map = {
        AgentRole.INCIDENT_RESPONSE: IncidentResponseAgent,
        AgentRole.THREAT_INTEL: ThreatIntelAgent,
        AgentRole.PREVENTION: PreventionAgent,
        AgentRole.COMPLIANCE: ComplianceAgent,
        # The Coordinator agent can be added here if it becomes a specialist
    }

    agent_pool: Dict[AgentRole, BaseSecurityAgent] = {}
    enabled_agent_configs = get_enabled_agents()

    for agent_config in enabled_agent_configs:
        role = agent_config["role"]

        if role in agent_class_map:
            AgentClass = agent_class_map[role]
            try:
                # Create an instance of the agent, injecting the shared clients
                agent_instance = AgentClass(llm_client=llm_client, mcp_client=mcp_client)
                agent_pool[role] = agent_instance
                logger.info(f"Successfully created agent: {agent_instance.name}")
            except Exception as e:
                logger.error(f"Failed to create agent for role {role.value}: {e}", exc_info=True)
        elif role != AgentRole.COORDINATOR: # Assuming Coordinator is handled separately
            logger.warning(f"No agent class found for enabled role: {role.value}")

    logger.info(f"Agent pool creation complete with {len(agent_pool)} agents.")
    return agent_pool
