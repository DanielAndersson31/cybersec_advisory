# agents/base_agent.py

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List
from langchain_openai import ChatOpenAI
from langfuse import observe
from pydantic import ValidationError
from langchain_core.messages import BaseMessage, SystemMessage

from config.agent_config import AgentRole, get_agent_config, get_agent_tools
from cybersec_mcp.cybersec_client import CybersecurityMCPClient
from workflow.schemas import StructuredAgentResponse

logger = logging.getLogger(__name__)


class BaseSecurityAgent(ABC):
    """
    The abstract base class for all cybersecurity specialist agents.

    This class provides a robust structure for agents that combine domain
    expertise (via system prompts) with real-time tool usage. It uses an
    LLM-driven approach for tool selection and structured response generation.
    """

    def __init__(
        self,
        role: AgentRole,
        llm_client: ChatOpenAI,
        mcp_client: CybersecurityMCPClient,
    ):
        """
        Initializes the agent with its role and injected dependencies.

        Args:
            role: The enum representing the agent's role (e.g., AgentRole.INCIDENT_RESPONSE).
            llm_client: An initialized ChatOpenAI client for language model calls.
            mcp_client: An initialized client for executing cybersecurity tools.
        """
        self.role = role
        self.config = get_agent_config(role)
        
        # Use LangChain's ChatOpenAI directly - no need for instructor patching
        self.llm = llm_client
        self.mcp_client = mcp_client

        # Core properties loaded from the configuration file.
        self.name: str = self.config["name"]
        self.model: str = self.config["model"]
        self.temperature: float = self.config.get("temperature", 0.1)
        self.max_tokens: int = self.config.get("max_tokens", 4000) # Increased for structured output

        # Gets the full JSON schema definitions for only the tools this agent is permitted to use.
        self.tools: List[Dict[str, Any]] = get_agent_tools(self.role)

        logger.info(
            f"Initialized agent: {self.name} ({self.role.value}) with {len(self.tools)} tools."
        )



    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        Returns the system prompt that defines the agent's persona and instructions.
        Must be implemented by each specialized agent subclass.
        """
        pass

    @observe(name="agent_respond")
    async def respond(self, messages: List[BaseMessage]) -> StructuredAgentResponse:
        """
        Generates a structured response using LangChain's native approach.
        
        Args:
            messages: List of LangChain BaseMessage objects
            
        Returns:
            Structured agent response
        """
        try:
            # Add system message to the beginning
            system_prompt = self.get_system_prompt()
            messages_with_system = [SystemMessage(content=system_prompt)] + messages

            # Use LangChain's structured output - this handles tool calling and structured output natively
            structured_llm = self.llm.with_structured_output(StructuredAgentResponse)
            
            # For now, let's use the simplified approach without tools
            # TODO: Add tool support back using LangChain's tool binding
            response = await structured_llm.ainvoke(messages_with_system)
            
            logger.info(f"Agent {self.name} generated response with confidence: {response.confidence_score:.2f}")
            return response

        except ValidationError as e:
            logger.error(f"Agent {self.name} failed validation: {e}", exc_info=True)
            return StructuredAgentResponse(
                summary=f"My response failed validation. Please review the error: {e}",
                recommendations=[],
                confidence_score=0.1,
                handoff_request=None
            )
        except Exception as e:
            logger.error(f"Agent {self.name} encountered an error: {e}", exc_info=True)
            return StructuredAgentResponse(
                summary=f"An unexpected error occurred: {e}",
                recommendations=[],
                confidence_score=0.0,
                handoff_request=None
            )

    async def _execute_tool(self, tool_name: str, kwargs: Dict[str, Any]) -> Any:
        """
        Executes a tool by mapping its name to the corresponding MCP client method.
        """
        tool_method_map = {
            "ioc_analysis_tool": self.mcp_client.analyze_ioc,
            "vulnerability_search_tool": self.mcp_client.search_vulnerabilities,
            "web_search_tool": self.mcp_client.search_web,
            "knowledge_search_tool": self.mcp_client.search_knowledge,
            "attack_surface_analyzer_tool": self.mcp_client.analyze_attack_surface,
            "threat_feeds_tool": self.mcp_client.get_threat_feeds,
            "compliance_guidance_tool": self.mcp_client.get_compliance_guidance,
        }

        if tool_name not in tool_method_map:
            return f"Error: Tool '{tool_name}' is not a valid or recognized tool."

        tool_method = tool_method_map[tool_name]

        try:
            return await tool_method(**kwargs)
        except Exception as e:
            logger.error(f"Error executing tool '{tool_name}': {e}", exc_info=True)
            return f"An error occurred while executing the tool: {e}"