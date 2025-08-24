# agents/base_agent.py

import logging
from abc import ABC, abstractmethod
from typing import List
from langchain_openai import ChatOpenAI
from langfuse import observe
from pydantic import ValidationError
from langchain_core.messages import BaseMessage, SystemMessage, ToolMessage, HumanMessage

from config.agent_config import AgentRole, get_agent_config, get_agent_tools
from cybersec_tools import CybersecurityToolkit
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
    ):
        """
        Initializes the agent with its role and injected dependencies.

        Args:
            role: The enum representing the agent's role (e.g., AgentRole.INCIDENT_RESPONSE).
            llm_client: An initialized ChatOpenAI client for language model calls.
        """
        self.role = role
        self.config = get_agent_config(role)
        
        # Store the base LLM and initialize toolkit
        self.base_llm = llm_client
        self.toolkit = CybersecurityToolkit()

        # Core properties loaded from the configuration file.
        self.name: str = self.config["name"]
        self.model: str = self.config["model"]
        self.temperature: float = self.config.get("temperature", 0.1)
        self.max_tokens: int = self.config.get("max_tokens", 4000) # Increased for structured output
        
        # Set up structured output LLM using LangChain's native capabilities
        self.structured_llm = llm_client.with_structured_output(StructuredAgentResponse)

        # Get tools directly from toolkit - much simpler!
        role_category = {
            AgentRole.INCIDENT_RESPONSE: "incident_response",
            AgentRole.THREAT_INTEL: "threat_intel", 
            AgentRole.PREVENTION: "prevention",
            AgentRole.COMPLIANCE: "compliance"
        }.get(role, "general")
        
        # Get role-specific tools plus general tools
        role_tools = self.toolkit.get_tools_by_category(role_category)
        general_tools = self.toolkit.get_tools_by_category("general")
        
        # Remove duplicates by tool name (StructuredTool objects aren't hashable)
        all_tools = role_tools + general_tools
        seen_names = set()
        self.tools = []
        for tool in all_tools:
            if tool.name not in seen_names:
                self.tools.append(tool)
                seen_names.add(tool.name)
        
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
                                # Direct tool invocation - no special handling needed
                                tool_result = await tool.ainvoke(tool_args)
                                
                                # Track tool usage
                                tool_usage_list.append(ToolUsage(
                                    tool_name=tool_name,
                                    tool_result=tool_result
                                ))
                                break
                            except Exception as e:
                                tool_result = f"Tool execution failed: {str(e)}"
                                logger.error(f"Tool {tool_name} failed: {e}")
                                
                                # Track failed tool usage
                                tool_usage_list.append(ToolUsage(
                                    tool_name=tool_name,
                                    tool_result=tool_result
                                ))
                    
                    # Add tool result to messages
                    messages_with_system.append(ToolMessage(
                        content=str(tool_result),
                        tool_call_id=tool_id
                    ))
                
                # Get final response with tool results
                response = await self.llm.ainvoke(messages_with_system)

            # Step 3: Generate structured output using instructor
            # Prepare conversation history for structured generation
            conversation_history = ""
            for msg in (messages_with_system + [response])[-4:]:  # Use last few messages for context
                if hasattr(msg, 'content'):
                    role_name = getattr(msg, '__class__', type(msg)).__name__
                    conversation_history += f"\n{role_name}: {msg.content}\n"
            
            structured_prompt = f"""
Based on the conversation above, provide a structured response as {self.name}.

Conversation History:
{conversation_history}

Include:
- A clear summary of your analysis
- Specific actionable recommendations  
- A confidence score (0.0-1.0) based on the available information
- Any handoff requests if other specialists should be involved

Provide a comprehensive response following the StructuredAgentResponse schema.
"""
            
            # Retry logic with LangChain structured output
            for attempt in range(3):
                try:
                    structured_response = await self.structured_llm.ainvoke([
                        SystemMessage(content=f"You are {self.name}. Provide structured analysis responses."),
                        HumanMessage(content=structured_prompt)
                    ])
                    break
                except Exception as e:
                    if attempt == 2:  # Last attempt
                        raise e
                    logger.warning(f"Structured response attempt {attempt + 1} failed for {self.name}: {e}, retrying...")
            
            # Add tool usage to the response
            structured_response.tools_used = tool_usage_list
            
            logger.info(f"Agent {self.name} generated response with confidence: {structured_response.confidence_score:.2f}, used {len(tool_usage_list)} tools")
            return structured_response

        except ValidationError as e:
            logger.error(f"Agent {self.name} failed validation after LangChain retries: {e}", exc_info=True)
            return StructuredAgentResponse(
                summary=f"My response failed validation after retries. Please review the error: {str(e)[:200]}",
                recommendations=["Please rephrase your query or try a simpler request"],
                confidence_score=0.1,
                handoff_request=None,
                tools_used=tool_usage_list
            )
        except Exception as e:
            logger.error(f"Agent {self.name} encountered an error after LangChain retries: {e}", exc_info=True)
            return StructuredAgentResponse(
                summary=f"An unexpected error occurred: {str(e)[:200]}",
                recommendations=["Please try your request again or contact support"],
                confidence_score=0.0,
                handoff_request=None,
                tools_used=tool_usage_list
            )

