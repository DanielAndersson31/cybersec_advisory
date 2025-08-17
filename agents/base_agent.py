# agents/base_agent.py

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List
import instructor
from openai import AsyncOpenAI
from langfuse import observe
from pydantic import ValidationError

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
        llm_client: AsyncOpenAI,
        mcp_client: CybersecurityMCPClient,
    ):
        """
        Initializes the agent with its role and injected dependencies.

        Args:
            role: The enum representing the agent's role (e.g., AgentRole.INCIDENT_RESPONSE).
            llm_client: An initialized AsyncOpenAI client for language model calls.
            mcp_client: An initialized client for executing cybersecurity tools.
        """
        self.role = role
        self.config = get_agent_config(role)
        
        # Patch the LLM client with instructor
        self.llm = instructor.patch(llm_client)
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
    async def respond(self, messages: List[Dict[str, Any]]) -> StructuredAgentResponse:
        """
        Generates a structured response by orchestrating LLM calls and tool execution.
        """
        system_prompt = self.get_system_prompt()
        messages_with_system = [{"role": "system", "content": system_prompt}, *messages]

        try:
            # Step 1: First LLM call to decide if tools are needed
            response = await self.llm.chat.completions.create(
                model=self.model,
                messages=messages_with_system,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                tools=self.tools if self.tools else None,
                tool_choice="auto" if self.tools else None,
            )
            response_message = response.choices[0].message

            # Step 2: Execute tools if the LLM requested them
            if response_message.tool_calls:
                messages_with_system.append(response_message)

                for tool_call in response_message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    
                    logger.info(f"Agent {self.name} calling tool '{tool_name}' with args: {tool_args}")
                    
                    tool_output = await self._execute_tool(tool_name, tool_args)
                    
                    messages_with_system.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": tool_name,
                        "content": str(tool_output),
                    })

            # Step 3: Final LLM call to generate a structured response
            final_response = await self.llm.chat.completions.create(
                model=self.model,
                messages=messages_with_system,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_model=StructuredAgentResponse,
                max_retries=2,
            )
            return final_response

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