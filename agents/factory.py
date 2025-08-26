# agents/factory.py

import logging
from typing import Dict
from openai import AsyncOpenAI
from langchain_openai import ChatOpenAI
from config import AgentRole, get_enabled_agents
from cybersec_mcp.cybersec_tools import CybersecurityToolkit
from agents.base_agent import BaseSecurityAgent
from agents.incident_responder import IncidentResponseAgent
from agents.threat_analyst import ThreatIntelAgent
from agents.prevention_specialist import PreventionAgent
from agents.compliance_specialist import ComplianceAgent
from agents.coordinator import CoordinatorAgent
from workflow.router import QueryRouter
from workflow.quality_gates import QualityGateSystem

logger = logging.getLogger(__name__)


class AgentFactory:
    """
    Handles the creation and dependency injection for all agents.
    """
    
    def __init__(self, llm_client: ChatOpenAI):
        """
        Initializes the factory with shared clients.
        
        Args:
            llm_client: A shared ChatOpenAI client for all agents.
        """
        self.llm_client = llm_client
        self.toolkit = CybersecurityToolkit()
        
        self.agent_class_map = {
            AgentRole.INCIDENT_RESPONSE: IncidentResponseAgent,
            AgentRole.THREAT_INTEL: ThreatIntelAgent,
            AgentRole.PREVENTION: PreventionAgent,
            AgentRole.COMPLIANCE: ComplianceAgent,
            AgentRole.COORDINATOR: CoordinatorAgent,
        }

    def create_agent(self, role: AgentRole) -> BaseSecurityAgent:
        """
        Creates a single agent with all dependencies injected.
        """
        AgentClass = self.agent_class_map.get(role)
        if not AgentClass:
            raise ValueError(f"No agent class found for role: {role}")
            
        try:
            # Create an instance of the agent, injecting the shared toolkit and client
            agent_instance = AgentClass(llm_client=self.llm_client, toolkit=self.toolkit)
            logger.info(f"Successfully created agent: {agent_instance.name}")
            return agent_instance
        except Exception as e:
            logger.error(f"Failed to create agent for role {role.value}: {e}", exc_info=True)
            raise

    def create_all_agents(self) -> Dict[AgentRole, BaseSecurityAgent]:
        """
        Creates a pool of all enabled specialist agents.
        """
        agent_pool: Dict[AgentRole, BaseSecurityAgent] = {}
        enabled_agent_configs = get_enabled_agents()

        for agent_config in enabled_agent_configs:
            role = agent_config["role"]
            if role in self.agent_class_map:
                agent_pool[role] = self.create_agent(role)
            else:
                logger.warning(f"No agent class found for enabled role: {role.value}")
        
        return agent_pool
    
    def create_router(self) -> "QueryRouter":
        """
        Creates a QueryRouter with necessary dependencies.
        """
        return QueryRouter(llm_client=self.llm_client, toolkit=self.toolkit)

    def create_quality_system(self) -> "QualityGateSystem":
        """
        Creates a QualityGateSystem with necessary dependencies.
        """
        return QualityGateSystem(llm_client=self.llm_client)
