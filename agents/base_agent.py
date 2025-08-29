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
from langchain_core.messages import HumanMessage

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
        
        # Log the actual tool names for debugging
        tool_names = [tool.name for tool in self.permitted_tools]
        logger.info(
            f"Initialized agent: {self.name} ({self.role.value}) with {len(self.permitted_tools)} tools: {tool_names}"
        )

    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        Returns the system prompt that defines the agent's persona and instructions.
        Must be implemented by each specialized agent subclass.
        """
        pass

    def _requires_tools_for_query(self, messages: List[Any]) -> bool:
        """
        Intelligent assessment of whether the current query requires tool usage.
        
        Args:
            messages: The conversation messages
            
        Returns:
            bool: True if tools are likely required, False if general knowledge suffices
        """
        # Get the main query content
        query_content = ""
        for msg in messages:
            if hasattr(msg, 'content') and msg.content:
                query_content = msg.content.lower()
                break
        
        # Indicators that tools are likely needed
        tool_required_indicators = [
            # Specific technical indicators
            'analyze', 'check', 'search', 'look up', 'investigate',
            # Specific IOCs or identifiers
            'ip address', 'domain', 'hash', 'url', 'cve-', 'email',
            # Current/recent information requests
            'latest', 'recent', 'current', 'new', 'today',
            # Specific compliance frameworks
            'gdpr', 'hipaa', 'pci-dss', 'sox', 'compliance check',
            # Vulnerability-specific requests
            'vulnerability', 'cve', 'patch', 'exploit'
        ]
        
        # Indicators that general knowledge may suffice
        general_knowledge_indicators = [
            # General questions
            'what is', 'what are', 'how to', 'explain', 'define',
            # General guidance requests
            'best practices', 'recommendations', 'approach', 'strategy',
            # Troubleshooting without specifics
            'weird task', 'strange process', 'suspicious activity',
            'high cpu', 'high ram', 'slow performance'
        ]
        
        # Check for tool-required indicators
        if any(indicator in query_content for indicator in tool_required_indicators):
            return True
            
        # Check for general knowledge indicators  
        if any(indicator in query_content for indicator in general_knowledge_indicators):
            return False
            
        # Default: lean toward allowing expertise without forced tools
        return False

    @observe(name="agent_respond")
    async def respond(self, messages: List[Any]) -> StructuredAgentResponse:
        """
        Generates a structured response by orchestrating LLM calls and tool execution.
        Includes intelligent tool usage assessment.
        """
        system_prompt = self.get_system_prompt()
        format_instructions = self.output_parser.get_format_instructions()
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", "{system_prompt}\n\n{format_instructions}"),
            MessagesPlaceholder(variable_name="messages"),
        ])
        
        llm_with_tools = self.llm.bind_tools(self.permitted_tools)
        logger.info(f"Agent {self.name} bound {len(self.permitted_tools)} tools to LLM: {[tool.name for tool in self.permitted_tools]}")
        
        # Debug: Log the system prompt characteristics
        logger.info(f"🔧 {self.name}: System prompt length: {len(system_prompt)} chars")
        
        chain = prompt | llm_with_tools
        
        message_history = list(messages)
        tools_used_info = []
        max_iterations = 5  # To prevent infinite loops
        
        logger.info(f"Agent {self.name} received {len(messages)} messages of types: {[type(msg).__name__ for msg in messages]}")
        
        # Debug: Log the content of the messages
        for i, msg in enumerate(messages):
            if hasattr(msg, 'content'):
                logger.info(f"🔧 {self.name}: Message {i} content preview: '{str(msg.content)[:100]}...'")
            else:
                logger.info(f"🔧 {self.name}: Message {i} type: {type(msg).__name__} (no content attribute)")

        for i in range(max_iterations):
            response = await chain.ainvoke({
                "system_prompt": system_prompt,
                "format_instructions": format_instructions,
                "messages": message_history
            })

            logger.info(f"🔍 {self.name}: Response length: {len(response.content) if response.content else 0} chars")
            logger.info(f"🔧 {self.name}: Tool calls detected: {hasattr(response, 'tool_calls') and bool(response.tool_calls)}")

            if not hasattr(response, 'tool_calls') or not response.tool_calls:
                # If no tool calls, we have the final answer
                final_content = response.content
                logger.info(f"ℹ️  {self.name}: No tools used - using direct expertise response")
                break

            # If there are tool calls, execute them
            message_history.append(response)
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                tool_id = tool_call["id"]
                
                logger.info(f"🔧 {self.name}: EXECUTING tool '{tool_name}' with args: {tool_args}")
                
                tool_output = await self._execute_tool(tool_name, tool_args)
                tools_used_info.append(
                    ToolUsage(tool_name=tool_name, tool_result=str(tool_output))
                )

                message_history.append(
                    ToolMessage(content=str(tool_output), tool_call_id=tool_id)
                )

            # After executing tools, check if we've reached the last iteration
            if i == max_iterations - 1:
                # If so, get the final response from the LLM
                final_response_message = await chain.ainvoke({
                    "system_prompt": system_prompt,
                    "format_instructions": format_instructions,
                    "messages": message_history
                })
                final_content = final_response_message.content
        
        else:
            # This block executes if the loop finishes without breaking (max_iterations reached)
            # We'll try to synthesize a response from the conversation history
            synthesis_prompt = "The investigation has reached its maximum iteration. Based on the information gathered from the tool calls, please provide a final summary and recommendations in the required JSON format."
            final_response_message = await chain.ainvoke({
                "system_prompt": system_prompt,
                "format_instructions": format_instructions,
                "messages": message_history + [HumanMessage(content=synthesis_prompt)]
            })
            final_content = final_response_message.content

        # Parse the final content into the structured format
        try:
            # Intelligent tool usage assessment - only require tools when truly necessary
            query_needs_tools = self._requires_tools_for_query(messages)
            
            if not tools_used_info and query_needs_tools:
                # Only reject if the query specifically requires tools
                logger.warning(f"⚠️  {self.name}: Query likely needs tools but none were used")
                # Don't reject - let the response go through but log the concern
                # This allows agents to provide expertise even without tools when appropriate
            
            if not tools_used_info:
                logger.info(f"✅ {self.name}: Providing expertise-based response without tools")
            
            # Always try to parse the response, regardless of tool usage
            parsed_response = await self.retry_parser.aparse(final_content)
            parsed_response.tools_used = tools_used_info
            
            # Adjust confidence based on tool usage for queries that might need them
            if not tools_used_info and query_needs_tools:
                # Slightly lower confidence for responses that might benefit from tools
                parsed_response.confidence_score = min(parsed_response.confidence_score, 0.8)
                logger.info(f"🔧 {self.name}: Adjusted confidence to {parsed_response.confidence_score} (no tools used)")
            
            logger.info(f"🎯 {self.name}: Final response summary length: {len(parsed_response.summary)} chars")
            logger.info(f"🎯 {self.name}: Final response has {len(parsed_response.recommendations)} recommendations")
            logger.info(f"🎯 {self.name}: Final response used {len(tools_used_info)} tools")
            logger.info(f"🎯 {self.name}: Final confidence score: {parsed_response.confidence_score}")
            
            return parsed_response
            
        except Exception as e:
            logger.error(f"Agent {self.name} could not parse the final response: {e}", exc_info=True)
            return StructuredAgentResponse(
                summary="I have completed my analysis, but encountered an issue formatting the final response.",
                recommendations=[],
                confidence_score=0.5,
                tools_used=tools_used_info
            )

    async def _execute_tool(self, tool_name: str, kwargs: Dict[str, Any]) -> Any:
        """
        Executes a tool from the toolkit by its name.
        """
        logger.info(f"🔧 {self.name}: ATTEMPTING tool '{tool_name}' with args: {kwargs}")
        
        tool = self.toolkit.get_tool_by_name(tool_name)
        if not tool:
            logger.error(f"Tool '{tool_name}' not found in toolkit. Available tools: {[t.name for t in self.toolkit.tools]}")
            return f"Error: Tool '{tool_name}' is not available in the toolkit."

        try:
            # ---> FIX: For web_search, ensure max_results is set to 5 <---
            if tool_name == "web_search":
                kwargs['max_results'] = 5  # Always fetch 5 results
                logger.info(f"🔧 {self.name}: Adjusted web_search max_results to {kwargs['max_results']}")

            # Asynchronously invoke the tool with provided arguments
            logger.info(f"🔧 {self.name}: EXECUTING tool '{tool_name}' with args: {kwargs}")
            result = await tool.ainvoke(kwargs)
            logger.info(f"✅ {self.name}: Tool '{tool_name}' SUCCESS - result type: {type(result)}")
            return result
        except Exception as e:
            logger.error(f"Error executing tool '{tool_name}': {e}", exc_info=True)
            return f"An error occurred while executing the tool: {e}"