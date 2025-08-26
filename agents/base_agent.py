# agents/base_agent.py

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from langchain_openai import ChatOpenAI
from langchain_core.messages import ToolMessage
from langfuse import observe
from langchain_core.tools import BaseTool
from langchain_core.output_parsers import PydanticOutputParser
from langchain.output_parsers.fix import OutputFixingParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from config.agent_config import AgentRole, get_agent_config, get_agent_tools
from cybersec_mcp.cybersec_tools import CybersecurityToolkit
from workflow.schemas import StructuredAgentResponse
from workflow.schemas import ToolUsage


logger = logging.getLogger(__name__)


class BaseSecurityAgent(ABC):
    """
    Base for all specialist agents, providing tool-handling and response generation.
    """

    def __init__(
        self,
        role: AgentRole,
        llm_client: ChatOpenAI,
        toolkit: CybersecurityToolkit,
    ):
        """
        Initializes the agent with its role and dependencies.

        Args:
            role: The agent's role (e.g., AgentRole.INCIDENT_RESPONSE).
            llm_client: LangChain ChatOpenAI client for language model calls.
            toolkit: The toolkit containing all available cybersecurity tools.
        """
        self.role = role
        self.config = get_agent_config(role)
        self.llm = llm_client
        self.toolkit = toolkit

        # Core properties from config
        self.name: str = self.config["name"]
        self.model: str = self.config["model"]
        self.temperature: float = self.config.get("temperature", 0.1)
        self.max_tokens: int = self.config.get("max_tokens", 4000)
        
        # Setup PydanticOutputParser for robust response structuring
        self.output_parser = PydanticOutputParser(pydantic_object=StructuredAgentResponse)
        
        # Use a retry mechanism to handle parsing errors
        self.retry_parser = OutputFixingParser.from_llm(
            parser=self.output_parser,
            llm=self.llm,
        )

        # Get permitted tools for this agent's role
        self.permitted_tools: List[BaseTool] = get_agent_tools(self.role, self.toolkit)
        
        logger.info(
            f"Initialized agent: {self.name} ({self.role.value}) with {len(self.permitted_tools)} tools."
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
        format_instructions = self.output_parser.get_format_instructions()
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", "{system_prompt}\n\n{format_instructions}"),
            MessagesPlaceholder(variable_name="messages"),
        ])
        
        # Bind permitted tools to the LLM and create the chain
        llm_with_tools = self.llm.bind_tools(self.permitted_tools)
        chain = prompt | llm_with_tools
        
        # The 'messages' from state are already BaseMessage objects, no conversion needed.
        
        try:
            # First LLM call to decide if tools are needed
            response = await chain.ainvoke({
                "system_prompt": system_prompt,
                "format_instructions": format_instructions,
                "messages": messages
            })

            # Execute tools if the LLM requested them
            if hasattr(response, 'tool_calls') and response.tool_calls:
                message_history = messages + [response]
                tools_used_info = []

                for tool_call in response.tool_calls:
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]
                    tool_id = tool_call["id"]
                    
                    logger.info(f"Agent {self.name} calling tool '{tool_name}' with args: {tool_args}")
                    
                    tool_output = await self._execute_tool(tool_name, tool_args)
                    tools_used_info.append(
                        ToolUsage(tool_name=tool_name, tool_result=str(tool_output))
                    )

                    message_history.append(
                        ToolMessage(content=str(tool_output), tool_call_id=tool_id)
                    )
                
                # Second LLM call with tool results for final synthesis
                final_response_message = await chain.ainvoke({
                    "system_prompt": system_prompt,
                    "format_instructions": format_instructions,
                    "messages": message_history
                })
                final_content = final_response_message.content
            else:
                final_content = response.content
                tools_used_info = []

            # Parse the final content into the structured format
            parsed_response = await self.retry_parser.aparse(final_content)
            parsed_response.tools_used = tools_used_info
            return parsed_response

        except Exception as e:
            logger.error(f"Agent {self.name} encountered an error: {e}", exc_info=True)
            return StructuredAgentResponse(
                summary=f"Error in {self.name}: I encountered a technical issue and couldn't complete your request. Please try again.",
                recommendations=[],
                confidence_score=0.0,
                tools_used=[]
            )

    async def _execute_tool(self, tool_name: str, kwargs: Dict[str, Any]) -> Any:
        """
        Executes a tool from the toolkit by its name.
        """
        tool = self.toolkit.get_tool_by_name(tool_name)
        if not tool:
            return f"Error: Tool '{tool_name}' is not available in the toolkit."

        try:
            # Asynchronously invoke the tool with provided arguments
            return await tool.ainvoke(kwargs)
        except Exception as e:
            logger.error(f"Error executing tool '{tool_name}': {e}", exc_info=True)
            return f"An error occurred while executing the tool: {e}"
