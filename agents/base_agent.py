# agents/base_agent.py

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from openai import AsyncOpenAI

# Assuming your config is accessible from a parent directory (e.g., ../config.py)
# This relative import path might need adjustment based on your project's root.
from ..config import AgentRole, get_agent_config, get_agent_tools

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    The abstract base class for all specialist agents in the system.

    This class provides the core structure for an agent, including initialization
    with role-specific configurations and an interface for analysis. It is designed
    to be invoked by an orchestration layer (e.g., a LangGraph node).
    """

    def __init__(self, role: AgentRole, client: AsyncOpenAI):
        """
        Initializes the agent with its specific role and a shared LLM client.

        This demonstrates dependency injection, making the agent more testable
        and efficient.

        Args:
            role: The enum representing the agent's role (e.g., AgentRole.INCIDENT_RESPONSE).
            client: An initialized AsyncOpenAI client for making API calls.
        """
        self.role = role
        self.config = get_agent_config(role)
        self.llm = client

        # Core properties are loaded from the configuration file, not hardcoded.
        self.name: str = self.config["name"]
        self.model: str = self.config["model"]
        self.temperature: float = self.config["temperature"]
        self.max_tokens: int = self.config["max_tokens"]

        # Gets the full definitions for the tools this agent is permitted to use.
        self.tools: List[Dict[str, Any]] = get_agent_tools(self.role)

        logger.info(f"Initialized agent: {self.name} ({self.role.value})")

    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        Returns the system prompt that defines the agent's persona and instructions.

        This method must be implemented by each specialized agent subclass, fulfilling
        the single responsibility principle.
        """
        pass

    async def analyze(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Performs analysis by calling the LLM with the agent's persona and tools.

        This method serves as the standard interface for the workflow to use.

        Args:
            messages: The current list of messages from the conversation state.

        Returns:
            The response dictionary from the LLM's message, which may include
            content for the user and/or tool_calls for the workflow to execute.
        """
        system_prompt = self.get_system_prompt()
        messages_with_system = [
            {"role": "system", "content": system_prompt},
            *messages,
        ]

        try:
            response = await self.llm.chat.completions.create(
                model=self.model,
                messages=messages_with_system,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                tools=self.tools if self.tools else None,
                tool_choice="auto" if self.tools else None,
            )
            # Return the message object, which contains 'content' and/or 'tool_calls'
            # The .model_dump() method converts it to a dictionary for the graph state.
            return response.choices[0].message.model_dump()

        except Exception as e:
            logger.error(
                f"Agent {self.name} encountered an API error: {e}", exc_info=True
            )
            # Return a structured error message for the workflow to handle gracefully.
            return {
                "role": "assistant",
                "content": f"I apologize, but I encountered an internal error and could not complete your request. (Error: {e})",
            }