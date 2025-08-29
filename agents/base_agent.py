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
from workflow.schemas import AgentResponse
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

        self.name: str = self.config["name"]
        self.model: str = self.config["model"]
        self.temperature: float = self.config.get("temperature", 0.1)
        self.max_tokens: int = self.config.get("max_tokens", 4000)
        
        self.output_parser = PydanticOutputParser(pydantic_object=AgentResponse)
        
        self.retry_parser = OutputFixingParser.from_llm(
            parser=self.output_parser,
            llm=self.llm,
        )

        self.permitted_tools: List[BaseTool] = get_agent_tools(self.role, self.toolkit)
        
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
        query_content = ""
        for msg in messages:
            if hasattr(msg, 'content') and msg.content:
                query_content = msg.content.lower()
                break
        
        tool_required_indicators = [
            'analyze', 'check', 'search', 'look up', 'investigate',
            'ip address', 'domain', 'hash', 'url', 'cve-', 'email',
            'latest', 'recent', 'current', 'new', 'today',
            'gdpr', 'hipaa', 'pci-dss', 'sox', 'compliance check',
            'vulnerability', 'cve', 'patch', 'exploit'
        ]
        
        general_knowledge_indicators = [
            'what is', 'what are', 'how to', 'explain', 'define',
            'best practices', 'recommendations', 'approach', 'strategy',
            'weird task', 'strange process', 'suspicious activity',
            'high cpu', 'high ram', 'slow performance'
        ]
        
        if any(indicator in query_content for indicator in tool_required_indicators):
            return True
            
        if any(indicator in query_content for indicator in general_knowledge_indicators):
            return False
            
        return False

    @observe(name="agent_respond")
    async def respond(self, messages: List[Any]) -> AgentResponse:
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
        logger.info(f"{self.name} initialized with {len(self.permitted_tools)} tools")
        
        chain = prompt | llm_with_tools
        
        message_history = list(messages)
        tools_used_info = []
        max_iterations = 5
        
        logger.info(f"{self.name} processing {len(messages)} messages")

        for i in range(max_iterations):
            response = await chain.ainvoke({
                "system_prompt": system_prompt,
                "format_instructions": format_instructions,
                "messages": message_history
            })

            if not hasattr(response, 'tool_calls') or not response.tool_calls:
                final_content = response.content
                break

            message_history.append(response)
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                tool_id = tool_call["id"]
                
                tool_output = await self._execute_tool(tool_name, tool_args)
                
                if hasattr(tool_output, 'model_dump_json'):
                    tool_result_str = tool_output.model_dump_json()
                elif hasattr(tool_output, 'content'):
                    tool_result_str = str(tool_output.content)
                elif hasattr(tool_output, 'summary'):
                    tool_result_str = str(tool_output.summary)
                else:
                    tool_result_str = str(tool_output)
                
                tools_used_info.append(
                    ToolUsage(tool_name=tool_name, tool_result=tool_result_str)
                )

                message_history.append(
                    ToolMessage(content=tool_result_str, tool_call_id=tool_id)
                )

            if i == max_iterations - 1:
                final_response_message = await chain.ainvoke({
                    "system_prompt": system_prompt,
                    "format_instructions": format_instructions,
                    "messages": message_history
                })
                final_content = final_response_message.content
        
        else:
            synthesis_prompt = "The investigation has reached its maximum iteration. Based on the information gathered from the tool calls, please provide a final summary and recommendations in the required JSON format."
            final_response_message = await chain.ainvoke({
                "system_prompt": system_prompt,
                "format_instructions": format_instructions,
                "messages": message_history + [HumanMessage(content=synthesis_prompt)]
            })
            final_content = final_response_message.content

        try:
            query_needs_tools = self._requires_tools_for_query(messages)
            
            if not tools_used_info and query_needs_tools:
                logger.warning(f"⚠️  {self.name}: Query likely needs tools but none were used")
            
            parsed_response = await self.retry_parser.aparse(final_content)
            parsed_response.tools_used = tools_used_info
            
            if not tools_used_info and query_needs_tools:
                parsed_response.confidence_score = min(parsed_response.confidence_score, 0.8)
            
            return parsed_response
            
        except Exception as e:
            logger.error(f"Agent {self.name} could not parse the final response: {e}", exc_info=True)
            return AgentResponse(
                summary="I have completed my analysis, but encountered an issue formatting the final response.",
                recommendations=[],
                confidence_score=0.5,
                tools_used=tools_used_info
            )

    async def _execute_tool(self, tool_name: str, kwargs: Dict[str, Any]) -> Any:
        """
        Executes a tool from the toolkit by its name.
        """
        tool = self.toolkit.get_tool_by_name(tool_name)
        if not tool:
            logger.error(f"Tool '{tool_name}' not found in toolkit. Available tools: {[t.name for t in self.toolkit.tools]}")
            return f"Error: Tool '{tool_name}' is not available in the toolkit."

        try:
            if tool_name == "web_search" and 'max_results' not in kwargs:
                kwargs['max_results'] = 5

            result = await tool.ainvoke(kwargs)
            return result
        except Exception as e:
            logger.error(f"Error executing tool '{tool_name}': {e}", exc_info=True)
            return f"An error occurred while executing the tool: {e}"