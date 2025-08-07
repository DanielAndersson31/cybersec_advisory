# agents/base_agent.py

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from openai import AsyncOpenAI
from langfuse.decorators import observe

# Assuming your config and cybersec_client are accessible from a parent directory.
# Adjust the import path based on your project's root structure.
from ..config import AgentRole, get_agent_config, get_agent_tools
from ..cybersec_client import CybersecurityMCPClient

logger = logging.getLogger(__name__)


class BaseSecurityAgent(ABC):
    """
    The abstract base class for all cybersecurity specialist agents.

    This class provides a robust structure for agents that combine domain
    expertise (via system prompts) with real-time tool usage. It uses an
    LLM-driven approach for tool selection, guided by a strict permission model.
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
        self.llm = llm_client
        self.mcp_client = mcp_client

        # Core properties loaded from the configuration file.
        self.name: str = self.config["name"]
        self.model: str = self.config["model"]
        self.temperature: float = self.config.get("temperature", 0.1)
        self.max_tokens: int = self.config.get("max_tokens", 2000)

        # Gets the full JSON schema definitions for only the tools this agent is permitted to use.
        # This filtered list is passed to the LLM, enforcing the permission layer.
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
    async def respond(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generates a response by orchestrating LLM calls and tool execution.

        This method implements a two-step, LLM-driven tool-calling loop.

        Args:
            messages: The current list of messages from the conversation state.

        Returns:
            The final response message object from the LLM.
        """
        system_prompt = self.get_system_prompt()
        messages_with_system = [{"role": "system", "content": system_prompt}, *messages]

        try:
            # === STEP 1: First LLM call to decide if tools are needed ===
            response = await self.llm.chat.completions.create(
                model=self.model,
                messages=messages_with_system,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                tools=self.tools if self.tools else None,
                tool_choice="auto" if self.tools else None,
            )
            response_message = response.choices[0].message

            # === STEP 2: Execute tools if the LLM requested them ===
            if response_message.tool_calls:
                messages_with_system.append(response_message)  # Add model's request to history

                for tool_call in response_message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    
                    logger.info(f"Agent {self.name} calling tool '{tool_name}' with args: {tool_args}")
                    
                    # Execute the tool and get the result
                    tool_output = await self._execute_tool(tool_name, tool_args)
                    
                    # Add the tool's result to the conversation history
                    messages_with_system.append(
                        {
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": tool_name,
                            "content": str(tool_output),
                        }
                    )
                
                # === STEP 3: Second LLM call with tool results for final synthesis ===
                final_response = await self.llm.chat.completions.create(
                    model=self.model,
                    messages=messages_with_system,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
                return final_response.choices[0].message.model_dump()

            # If no tools were called, return the first response
            return response_message.model_dump()

        except Exception as e:
            logger.error(f"Agent {self.name} encountered an error: {e}", exc_info=True)
            return {"role": "assistant", "content": f"Error in {self.name}: {e}"}

    async def _execute_tool(self, tool_name: str, kwargs: Dict[str, Any]) -> Any:
        """
        Executes a tool by mapping its name to the corresponding MCP client method.

        This acts as a secure and maintainable router, preventing the LLM from
        calling arbitrary code.
        """
        # Mapping from the tool name in config to the actual client method.
        tool_method_map = {
            "ioc_analysis_tool": self.mcp_client.analyze_ioc,
            "vulnerability_search_tool": self.mcp_client.search_vulnerabilities,
            "web_search_tool": self.mcp_client.search_web,
            "knowledge_search_tool": self.mcp_client.search_knowledge,
            "breach_monitoring_tool": self.mcp_client.monitor_breaches,
            "attack_surface_analyzer_tool": self.mcp_client.analyze_attack_surface,
            "threat_feeds_tool": self.mcp_client.get_threat_feeds,
            "compliance_guidance_tool": self.mcp_client.get_compliance_guidance,
        }

        if tool_name not in tool_method_map:
            return f"Error: Tool '{tool_name}' is not a valid or recognized tool."

        # Get the correct client method from the map
        tool_method = tool_method_map[tool_name]

        try:
            # Call the method with the arguments provided by the LLM
            return await tool_method(**kwargs)
        except Exception as e:
            logger.error(f"Error executing tool '{tool_name}': {e}", exc_info=True)
            return f"An error occurred while executing the tool: {e}"