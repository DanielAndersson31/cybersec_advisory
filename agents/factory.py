import logging
from typing import Dict
from langchain_openai import ChatOpenAI
from config.agent_config import AgentRole, get_enabled_agents
from cybersec_mcp.cybersec_tools import CybersecurityToolkit
from agents.base_agent import BaseSecurityAgent
from agents.prompts import AgentPrompts
from workflow.router import QueryRouter
from workflow.quality_gates import QualityGateSystem
from knowledge.knowledge_retrieval import create_knowledge_retriever

logger = logging.getLogger(__name__)


class DynamicSecurityAgent(BaseSecurityAgent):
    """
    Dynamic agent that gets its system prompt injected at creation time.
    Eliminates the need for separate agent subclasses.
    """
    
    def __init__(self, role: AgentRole, llm_client: ChatOpenAI, toolkit: CybersecurityToolkit, system_prompt: str):
        super().__init__(role, llm_client, toolkit)
        self._system_prompt = system_prompt
    
    def get_system_prompt(self) -> str:
        return self._system_prompt


class AgentFactory:
    """
    Handles the creation and dependency injection for all agents.
    Now uses centralized prompts and dynamic agent creation.
    """
    
    def __init__(self, llm_client: ChatOpenAI):
        """
        Initializes the factory with shared clients and dependencies.
        
        Args:
            llm_client: A shared ChatOpenAI client for all agents.
        """
        self.llm_client = llm_client
        
        self.knowledge_retriever = create_knowledge_retriever()
        self.toolkit = CybersecurityToolkit(knowledge_retriever=self.knowledge_retriever)
        
        logger.info("AgentFactory initialized with proper dependency injection")

    def create_agent(self, role: AgentRole) -> BaseSecurityAgent:
        """
        Creates a single agent with all dependencies injected.
        Now uses centralized prompts and dynamic agent creation.
        """
        try:
            system_prompt = AgentPrompts.get_prompt(role)
            
            agent_instance = DynamicSecurityAgent(
                role=role,
                llm_client=self.llm_client,
                toolkit=self.toolkit,
                system_prompt=system_prompt
            )
            logger.info(f"Successfully created agent: {agent_instance.name}")
            return agent_instance
        except Exception as e:
            logger.error(f"Failed to create agent for role {role.value}: {e}", exc_info=True)
            raise

    def create_all_agents(self) -> Dict[AgentRole, BaseSecurityAgent]:
        """
        Creates a pool of all enabled specialist agents using dynamic creation.
        """
        agent_pool: Dict[AgentRole, BaseSecurityAgent] = {}
        enabled_agent_configs = get_enabled_agents()

        for agent_config in enabled_agent_configs:
            role = agent_config["role"]
            try:
                agent_pool[role] = self.create_agent(role)
            except Exception as e:
                logger.error(f"Failed to create agent for role {role.value}: {e}")
        
        logger.info(f"Created {len(agent_pool)} agents successfully")
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
