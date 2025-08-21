# agents/base_agent.py

import logging
from abc import ABC, abstractmethod
from typing import List
from langchain_openai import ChatOpenAI
from langfuse import observe
from pydantic import ValidationError
from langchain_core.messages import BaseMessage, SystemMessage, ToolMessage

from config.agent_config import AgentRole, get_agent_config, get_agent_tools
from cybersec_mcp.cybersec_client import CybersecurityMCPClient
from workflow.schemas import StructuredAgentResponse, ToolUsage

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
        
        # Store the base LLM and MCP client
        self.base_llm = llm_client
        self.mcp_client = mcp_client

        # Core properties loaded from the configuration file.
        self.name: str = self.config["name"]
        self.model: str = self.config["model"]
        self.temperature: float = self.config.get("temperature", 0.1)
        self.max_tokens: int = self.config.get("max_tokens", 4000) # Increased for structured output

        # Get LangChain tools from MCP client and bind to LLM
        available_tools = self.mcp_client.get_langchain_tools()
        
        # Filter tools based on agent permissions (from config)
        permitted_tool_names = [tool["function"]["name"] for tool in get_agent_tools(self.role)]
        self.tools = [tool for tool in available_tools if tool.name in permitted_tool_names]
        
        # Create LLM with tools bound
        self.llm = self.base_llm.bind_tools(self.tools) if self.tools else self.base_llm

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
        Generates a structured response using LangChain's native approach with tool calling.
        
        Args:
            messages: List of LangChain BaseMessage objects
            
        Returns:
            Structured agent response with tool usage tracking
        """
        tool_usage_list = []  # Track tools used during this response
        
        try:
            # Add system message to the beginning
            system_prompt = self.get_system_prompt()
            messages_with_system = [SystemMessage(content=system_prompt)] + messages

            # Step 1: Let the LLM decide if it needs to use tools
            response = await self.llm.ainvoke(messages_with_system)
            
            # Step 2: Handle tool calls if any
            if response.tool_calls:
                logger.info(f"Agent {self.name} is calling {len(response.tool_calls)} tools")
                
                # Add the AI response with tool calls to the message history
                messages_with_system.append(response)
                
                # Execute each tool call
                for tool_call in response.tool_calls:
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]
                    tool_id = tool_call["id"]
                    
                    logger.info(f"Executing tool: {tool_name} with args: {tool_args}")
                    
                    # Find and execute the tool
                    tool_result = "Tool not found"
                    for tool in self.tools:
                        if tool.name == tool_name:
                            try:
                                tool_result = await tool.ainvoke(tool_args)
                                
                                # Track tool usage
                                tool_usage_list.append(ToolUsage(
                                    tool_name=tool_name,
                                    tool_args=tool_args,
                                    tool_result=tool_result
                                ))
                                break
                            except Exception as e:
                                tool_result = f"Tool execution failed: {str(e)}"
                                logger.error(f"Tool {tool_name} failed: {e}")
                                
                                # Track failed tool usage
                                tool_usage_list.append(ToolUsage(
                                    tool_name=tool_name,
                                    tool_args=tool_args,
                                    tool_result=tool_result
                                ))
                    
                    # Add tool result to messages
                    messages_with_system.append(ToolMessage(
                        content=str(tool_result),
                        tool_call_id=tool_id
                    ))
                
                # Get final response with tool results
                response = await self.llm.ainvoke(messages_with_system)

            # Step 3: Generate structured output from the final response
            structured_llm = self.base_llm.with_structured_output(StructuredAgentResponse)
            
            # Create a prompt that includes the conversation and asks for structured output
            final_messages = messages_with_system + [response] if response.tool_calls else messages_with_system + [response]
            
            # Add instruction for structured output
            structured_prompt = SystemMessage(content=f"""
Based on the conversation above, provide a structured response as {self.name}.
Include:
- A clear summary of your analysis
- Specific actionable recommendations
- A confidence score (0.0-1.0) based on the available information
- Any handoff requests if other specialists should be involved

Format your response according to the StructuredAgentResponse schema.
""")
            
            structured_response = await structured_llm.ainvoke([structured_prompt] + final_messages[-3:])  # Use last few messages for context
            
            # Add tool usage to the response
            structured_response.tools_used = tool_usage_list
            
            logger.info(f"Agent {self.name} generated response with confidence: {structured_response.confidence_score:.2f}, used {len(tool_usage_list)} tools")
            return structured_response

        except ValidationError as e:
            logger.error(f"Agent {self.name} failed validation: {e}", exc_info=True)
            return StructuredAgentResponse(
                summary=f"My response failed validation. Please review the error: {e}",
                recommendations=[],
                confidence_score=0.1,
                handoff_request=None,
                tools_used=tool_usage_list
            )
        except Exception as e:
            logger.error(f"Agent {self.name} encountered an error: {e}", exc_info=True)
            return StructuredAgentResponse(
                summary=f"An unexpected error occurred: {e}",
                recommendations=[],
                confidence_score=0.0,
                handoff_request=None,
                tools_used=tool_usage_list
            )

