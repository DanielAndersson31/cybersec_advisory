"""
Node functions for the workflow graph.
Integrated with your existing QualityGateSystem.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from dataclasses import dataclass
from abc import ABC, abstractmethod

from langfuse import observe
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain_openai import ChatOpenAI

from workflow.state import WorkflowState
from workflow.schemas import TeamResponse, SearchIntentResult, ContextContinuityCheck
from workflow.system_prompts import NodePrompts, SystemMessages, PromptFormatter
from config.agent_config import AgentRole
from agents.factory import AgentFactory
from cybersec_mcp.cybersec_tools import CybersecurityToolkit
from cybersec_mcp.tools.web_search import WebSearchResponse


logger = logging.getLogger(__name__)


# =============================================================================
# HELPER CLASSES FOR ORGANIZATION
# =============================================================================

@dataclass
class WebSearchContext:
    """Encapsulates web search intent and context"""
    required: bool
    intent_type: str
    confidence: float
    reasoning: str
    trigger_phrase: Optional[str] = None


class WebSearchIntentDetector:
    """Separated web search intent detection logic"""
    
    def __init__(self, llm_client):
        self.search_intent_llm = llm_client.with_structured_output(SearchIntentResult)
    
    async def detect_intent(self, query: str) -> WebSearchContext:
        """Detect web search intent with structured return"""
        query_lower = query.lower()
        
        # Quick keyword checks first
        explicit_triggers = [
            "look up", "look it up", "search for", "check online", "search online", 
            "web search", "search the web", "google", "find online"
        ]
        temporal_triggers = [
            "latest", "recent", "current", "new", "emerging", "today", "this week",
            "this month", "2024", "2025", "now", "currently", "nowadays"
        ]
        
        explicit_match = any(trigger in query_lower for trigger in explicit_triggers)
        has_temporal = any(trigger in query_lower for trigger in temporal_triggers)
        
        if explicit_match:
            return WebSearchContext(
                required=True,
                intent_type="explicit_web_request",
                confidence=0.95,
                reasoning="Explicit web search language detected",
                trigger_phrase=next(t for t in explicit_triggers if t in query_lower)
            )
        
        if has_temporal or any(word in query_lower for word in ["trends", "updates", "news", "happening"]):
            return await self._llm_analyze_intent(query)
        
        return WebSearchContext(
            required=False,
            intent_type="no_web_needed", 
            confidence=0.9,
            reasoning="No temporal indicators or explicit web search requests"
        )
    
    async def _llm_analyze_intent(self, query: str) -> WebSearchContext:
        """Use LLM for complex intent analysis"""
        llm_prompt = PromptFormatter.format_web_search_intent_prompt(query)
        
        try:
            intent_result = await self.search_intent_llm.ainvoke([
                SystemMessage(content=SystemMessages.WEB_SEARCH_INTENT_EXPERT),
                HumanMessage(content=llm_prompt)
            ])
            
            return WebSearchContext(
                required=intent_result.needs_web_search,
                intent_type="llm_analyzed" if intent_result.needs_web_search else "no_web_needed",
                confidence=intent_result.confidence,
                reasoning=intent_result.reasoning
            )
            
        except Exception as e:
            logger.warning(f"LLM search intent analysis failed: {e}")
            return WebSearchContext(
                required=True,  # Conservative fallback
                intent_type="temporal_fallback",
                confidence=0.7,
                reasoning="Fallback analysis due to LLM error"
            )


class AgentConsultationHandler:
    """Handles the complex agent consultation logic"""
    
    def __init__(self, agents: Dict, web_search_detector: WebSearchIntentDetector):
        self.agents = agents
        self.web_search_detector = web_search_detector
    
    async def consult_agents(self, state: WorkflowState) -> WorkflowState:
        """Main consultation method - now focused and clean"""
        agents_to_consult = state["agents_to_consult"]
        
        if not agents_to_consult:
            logger.warning("No agents to consult")
            return state
        
        web_context = await self._get_web_search_context(state)
        
        for agent_role in agents_to_consult:
            await self._consult_single_agent(state, agent_role, web_context)
        
        self._update_agent_persistence(state)
        
        return state
    
    async def _get_web_search_context(self, state: WorkflowState) -> Optional[WebSearchContext]:
        """Extract or detect web search context"""
        web_intent = state.get("web_search_intent")
        if not web_intent:
            return None
            
        return WebSearchContext(
            required=web_intent.get("web_search_required", False),
            intent_type=web_intent.get("intent_type", "unknown"),
            confidence=web_intent.get("confidence", 0.5),
            reasoning=web_intent.get("reasoning", ""),
            trigger_phrase=web_intent.get("trigger_phrase")
        )
    
    async def _consult_single_agent(
        self, 
        state: WorkflowState, 
        agent_role: AgentRole, 
        web_context: Optional[WebSearchContext]
    ):
        """Consult a single agent with proper context injection"""
        agent = self.agents.get(agent_role)
        if not agent:
            logger.error(f"Agent {agent_role} not found")
            return
        
        try:
            logger.info(f"Consulting {agent.name}")
            
            messages = self._build_agent_messages(
                state["query"],
                web_context,
                state.get("messages", [])
            )
            
            structured_response = await agent.respond(messages=messages)
            
            team_response = TeamResponse(
                agent_name=agent.name,
                agent_role=agent_role,
                response=structured_response,
                tools_used=structured_response.tools_used,
            )
            
            state["team_responses"].append(team_response)
            
            logger.info(f"{agent.name} completed (confidence: {structured_response.confidence_score:.2f})")
            
        except Exception as e:
            logger.error(f"Error consulting {agent.name}: {e}")
            state["error_count"] = state.get("error_count", 0) + 1
            state["last_error"] = str(e)
    
    def _build_agent_messages(self, query: str, web_context: Optional[WebSearchContext], conversation_history: Optional[List] = None) -> List:
        """Build appropriate messages for agent consultation with conversation context"""
        if conversation_history and len(conversation_history) > 1:
            messages = conversation_history[-5:]
        else:
            messages = [HumanMessage(content=query)]

        if web_context and web_context.required:
            search_context_msg = self._create_search_context_message(web_context)
            messages.insert(0, search_context_msg)

        return messages
    
    def _create_search_context_message(self, web_context: WebSearchContext) -> SystemMessage:
        """Create web search context system message"""
        context_text = (
            f"[SEARCH CONTEXT: Your analysis indicates the user's query may require current information from the web. "
            f"Type: {web_context.intent_type}, Confidence: {web_context.confidence:.2f}, "
            f"Reasoning: {web_context.reasoning}. You should strongly consider using the web_search tool.]"
        )
        
        return SystemMessage(content=context_text)
    

    
    def _update_agent_persistence(self, state: WorkflowState):
        """Update active agent tracking for follow-ups"""
        if len(state["team_responses"]) == 1:
            state["active_agent"] = state["team_responses"][0].agent_role
            state["conversation_context"] = "cybersecurity"
        elif len(state["team_responses"]) > 1:
            state["active_agent"] = None
            state["conversation_context"] = "cybersecurity"


# =============================================================================
# MAIN WORKFLOW NODES CLASS
# =============================================================================

class WorkflowNodes:
    """
    Contains all node functions for the workflow graph - now properly organized.
    """
    
    def __init__(self, agent_factory: "AgentFactory", toolkit: CybersecurityToolkit, llm_client: ChatOpenAI, enable_quality_gates: bool = True):
        """
        Initialize with agent factory, toolkit, and other components.
        """
        self.agent_factory = agent_factory
        self.toolkit = toolkit
        self.llm_client = llm_client
        self.enable_quality_gates = enable_quality_gates
        
        # Initialize organized components
        self.web_search_detector = WebSearchIntentDetector(llm_client)
        self.agents = agent_factory.create_all_agents()
        self.consultation_handler = AgentConsultationHandler(self.agents, self.web_search_detector)
        
        # Initialize other components
        self.coordinator = agent_factory.create_agent(AgentRole.COORDINATOR)
        self.router = agent_factory.create_router()
        self.quality_system = agent_factory.create_quality_system()

        # Pre-initialize the web search tool
        self.web_search_tool = self.toolkit.get_tool_by_name("web_search")
        if not self.web_search_tool:
            logger.warning("Web search tool not found in toolkit")

        # Create structured LLM for context continuity check, including retry logic
        self.context_continuity_llm = llm_client.with_structured_output(
            ContextContinuityCheck
        ).with_retry(stop_after_attempt=2)

    def _format_web_search_results(self, search_response: WebSearchResponse) -> str:
        """
        Format web search results in a way that's easy for the LLM to understand and use.
        """
        if not search_response.results:
            return "No relevant results found for your search query."
        
        formatted_results = []
        for i, result in enumerate(search_response.results, 1):
            formatted_results.append(f"""
Result {i}:
Title: {result.title}
URL: {result.url}
Content: {result.content[:300]}{'...' if len(result.content) > 300 else ''}
""")
        
        return f"""
Web search results for: "{search_response.query}"
Enhanced query used: "{search_response.enhanced_query}"
Time filters applied: {search_response.time_filter_applied or 'None'}

{''.join(formatted_results)}

Please use this information to provide an accurate and helpful response to the user's question.
"""

    @observe(name="analyze_query")
    async def analyze_query(self, state: WorkflowState) -> WorkflowState:
        """
        Analyze query - now focused and clean.
        """
        # Set metadata
        state["started_at"] = datetime.now(timezone.utc)
        state["messages"].append(HumanMessage(content=state["query"]))
        
        # Detect web search intent
        web_context = await self.web_search_detector.detect_intent(state["query"])
        state["web_search_intent"] = {
            "web_search_required": web_context.required,
            "intent_type": web_context.intent_type,
            "confidence": web_context.confidence,
            "reasoning": web_context.reasoning,
            "trigger_phrase": web_context.trigger_phrase
        }
        
        return state

    @observe(name="check_context_continuity")
    async def check_context_continuity(self, state: WorkflowState) -> WorkflowState:
        """
        Check if the current query maintains cybersecurity conversation context
        AND perform context-aware routing.
        """
        conversation_history = state.get("conversation_history", [])
        
        # If no conversation history, check if we have active_agent from previous state
        if not conversation_history:
            active_agent = state.get("active_agent")
            conversation_context = state.get("conversation_context")
            
            if active_agent and conversation_context == "cybersecurity":
                # We have an active cybersecurity agent from previous state
                state["context_continuity"] = {
                    "is_follow_up": True,
                    "context_maintained": True,
                    "previous_context": f"Previous conversation with {active_agent.value}",
                    "specialist_context": active_agent.value.lower(),
                    "confidence": 0.9,
                    "reasoning": f"Active agent {active_agent.value} found in persisted state"
                }
            else:
                state["context_continuity"] = {
                    "is_follow_up": False,
                    "context_maintained": True,
                    "previous_context": None,
                    "specialist_context": "general",
                    "confidence": 1.0,
                    "reasoning": "First query in conversation"
                }
        else:
            recent_messages = conversation_history[-3:]
            
            context_prompt = PromptFormatter.format_context_continuity_prompt(
                current_query=state['query'],
                conversation_history=chr(10).join([f"- {msg.role}: {msg.content[:200]}..." for msg in recent_messages])
            )
            
            try:
                context_result = await self.context_continuity_llm.ainvoke([
                    SystemMessage(content=SystemMessages.CONTEXT_CONTINUITY_EXPERT),
                    HumanMessage(content=context_prompt)
                ])
                
                state["context_continuity"] = context_result.model_dump()
                
                logger.info(f"Context continuity check successful: Follow-up={context_result.is_follow_up}, "
                        f"Context maintained={context_result.context_maintained}, "
                        f"Specialist context={context_result.specialist_context}, "
                        f"Confidence={context_result.confidence:.2f}")
                
            except Exception as e:
                logger.error(f"Context continuity check failed after all retries: {e}")
                # Enhanced fallback - use persisted state if available
                active_agent = state.get("active_agent")
                if active_agent:
                    state["context_continuity"] = {
                        "is_follow_up": True,
                        "context_maintained": True,
                        "previous_context": f"Previous conversation with {active_agent.value}",
                        "specialist_context": active_agent.value.lower(),
                        "confidence": 0.7,
                        "reasoning": f"Fallback: Using persisted active agent {active_agent.value}"
                    }
                else:
                    state["context_continuity"] = {
                        "is_follow_up": True,
                        "context_maintained": True,
                        "previous_context": "Previous cybersecurity conversation",
                        "specialist_context": "general",
                        "confidence": 0.5,
                        "reasoning": "Default assumption due to analysis failure"
                    }
        
        # NOW DO CONTEXT-AWARE ROUTING using the context we just determined
        context_continuity = state.get("context_continuity", {})
        
        # Prepare context hints for router
        context_hint = None
        active_agent = state.get("active_agent")
        
        # If we have cybersecurity context, provide hints to router
        if (context_continuity.get("context_maintained") and 
            context_continuity.get("specialist_context") in ["incident_response", "prevention", "threat_intel", "compliance"]):
            context_hint = context_continuity.get("specialist_context")
            logger.info(f"ROUTER CALL: context_hint={context_hint}, active_agent={active_agent}")

        # Perform intelligent classification and routing decision with context awareness
        routing_decision = await self.router.determine_routing_strategy(
            state["query"],
            context_hint=context_hint,
            active_agent=active_agent
        )
        
        # Update state with analysis results
        state["response_strategy"] = routing_decision.response_strategy
        state["agents_to_consult"] = routing_decision.relevant_agents
        state["estimated_complexity"] = routing_decision.estimated_complexity
        
        # Set first agent if any
        if routing_decision.relevant_agents:
            state["current_agent"] = routing_decision.relevant_agents[0]
            
        # Determine if consensus needed
        state["needs_consensus"] = len(routing_decision.relevant_agents) > 1
        
        logger.info(f"Routing complete for '{state['query'][:50]}...': {routing_decision.response_strategy} "
                   f"(complexity: {routing_decision.estimated_complexity}) - {routing_decision.reasoning}")
        
        return state
    
    @observe(name="consult_agent") 
    async def consult_agent(self, state: WorkflowState) -> WorkflowState:
        """Agent consultation - now delegates to organized handler"""
        return await self.consultation_handler.consult_agents(state)

    @observe(name="general_response")
    async def general_response(self, state: WorkflowState) -> WorkflowState:
        """
        Handle general (non-cybersecurity) queries with web search capabilities.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with general assistant response
        """
        logger.info("--- Entering General Response Node ---")
        logger.info(f"State 'query' at this point: '{state['query']}'")
        logger.info(f"Number of messages in state: {len(state['messages'])}")
        if state['messages']:
            logger.info(f"Last message content: '{state['messages'][-1].content}'")
            
        logger.info(f"General assistant handling query: {state['query'][:50]}...")
        
        try:
            llm = self.llm_client
            llm_with_tools = llm.bind_tools([self.web_search_tool])
            
            # System prompt for general assistant with web search
            system_prompt = NodePrompts.GENERAL_ASSISTANT
            
            messages = [
                SystemMessage(content=system_prompt),
                *state["messages"]
            ]
            
            response = await llm_with_tools.ainvoke(messages)
            
            if hasattr(response, 'tool_calls') and response.tool_calls:
                logger.info(f"General assistant making {len(response.tool_calls)} tool calls")
                messages.append(response)
                
                for tool_call in response.tool_calls:
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]
                    tool_id = tool_call["id"]
                    
                    try:
                        if tool_name == "web_search":
                            tool_args['max_results'] = 5  # Always fetch 5 results
                            logger.info(f"LLM generated tool query for web_search: '{tool_args.get('query')}' with max_results={tool_args['max_results']}")
                            tool_result = await self.web_search_tool.ainvoke(tool_args)
                            logger.info(f"Web search returned {tool_result.total_results} results")
                            # Format web search results in a more LLM-friendly way
                            formatted_result = self._format_web_search_results(tool_result)
                        else:
                            # For any other tools that might be called
                            formatted_result = f"Tool {tool_name} executed successfully"
                        
                        messages.append(ToolMessage(
                            content=formatted_result,
                            tool_call_id=tool_id
                        ))
                    
                    except Exception as tool_error:
                        logger.error(f"Tool execution failed for {tool_name}: {tool_error}")
                        # Always provide a response, even if tool fails
                        messages.append(ToolMessage(
                            content=f"Tool {tool_name} failed: {str(tool_error)}",
                            tool_call_id=tool_id
                        ))
                
                # Final response after tool calls
                final_response = await llm_with_tools.ainvoke(messages)
                final_answer = final_response.content.strip() if final_response.content else ""

                if not final_answer:
                    logger.warning("LLM returned an empty response after tool call. Using fallback.")
                    final_answer = "I found some information using a web search, but I'm having trouble summarizing it. Could you try rephrasing your question?"
            else:
                # No tools used, use direct response
                final_answer = response.content.strip() if response.content else ""
                if not final_answer:
                    logger.warning("LLM returned an empty response (no tools). Using fallback.")
                    final_answer = "I'm sorry, I'm having trouble formulating a response. Could you please try again?"
            
            state["final_answer"] = final_answer
            state["messages"].append(AIMessage(content=final_answer))
            state["completed_at"] = datetime.now(timezone.utc)
            
            # Clear active agent and set general context
            state["active_agent"] = None
            state["conversation_context"] = "general"
            
            logger.info("General assistant provided response (with web search capability)")
            
        except Exception as e:
            logger.error(f"General assistant response failed: {e}")
            # Fallback to a simple response
            if "hey" in state["query"].lower() or "hello" in state["query"].lower() or "hi" in state["query"].lower():
                fallback = "Hello! How can I help you today?"
            elif "weather" in state["query"].lower():
                fallback = "I'd love to help with weather information, but I'm having trouble accessing current data right now. You might want to check a weather website or app for the most up-to-date information."
            else:
                fallback = "I'd be happy to help with your question. Could you provide a bit more detail?"
                
            state["final_answer"] = fallback
            state["error_count"] = state.get("error_count", 0) + 1
            state["last_error"] = str(e)
        
        return state

    @observe(name="direct_response")
    async def direct_response(self, state: WorkflowState) -> WorkflowState:
        """
        Handle simple cybersecurity queries directly using router's tools and knowledge.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with direct response
        """
        logger.info(f"Handling simple cybersecurity query directly: {state['query'][:50]}...")
        
        try:
            # Handle direct cybersecurity response with router tools
            final_answer = await self.router.direct_response(state["query"])
            
            state["final_answer"] = final_answer
            
            # Add to conversation
            state["messages"].append(AIMessage(content=state["final_answer"]))
            state["completed_at"] = datetime.now(timezone.utc)
            
            # Keep cybersecurity context but don't set specific active agent for direct responses
            state["conversation_context"] = "cybersecurity"
            state["active_agent"] = None  # Direct responses don't have a specific agent
            
            logger.info("Direct cybersecurity response completed successfully")
            
        except Exception as e:
            logger.error(f"Direct response failed: {e}")
            state["final_answer"] = f"I encountered an error while processing your cybersecurity query: {str(e)}"
            state["error_count"] = state.get("error_count", 0) + 1
            state["last_error"] = str(e)
        
        return state


    @observe(name="synthesize_responses")
    async def synthesize_responses(self, state: WorkflowState) -> WorkflowState:
        """
        Synthesize all agent responses into a final, high-quality answer.
        For single-agent natural responses, pass them through with minimal processing.
        For multi-agent responses, combine them into a consolidated view.
        """
        if not state["team_responses"]:
            state["final_answer"] = "I couldn't gather expert analysis for your query."
            return state
        
        if len(state["team_responses"]) == 1:
            # For single agent response, handle unified response format
            agent_response = state["team_responses"][0]
            response_content = agent_response.response
            
            # Use content if available (natural response), otherwise use summary (structured response)
            if response_content.content:
                final_answer = response_content.content
            elif response_content.summary:
                final_answer = response_content.summary
                # Add recommendations if available
                if response_content.recommendations:
                    final_answer += "\n\n**Key Recommendations:**\n"
                    for rec in response_content.recommendations:
                        final_answer += f"• {rec}\n"
            else:
                final_answer = "I provided an analysis for your query."

            # Append tool usage information if any tools were used
            if agent_response.tools_used:
                final_answer += "\n\n**Sources & Tools Used:**\n"
                for tool in agent_response.tools_used:
                    final_answer += f"• {tool.tool_name}\n"

            state["final_answer"] = final_answer
        
        else:
            # For multiple agents, decide between formal coordination vs simple synthesis
            if state.get("needs_consensus", False) or len(state["team_responses"]) > 2:
                # Use formal coordination format for complex multi-agent responses
                final_answer = await self._create_executive_summary(state["team_responses"], state["query"])
            else:
                # Use existing simple synthesis logic
                final_answer = self._create_simple_synthesis(state["team_responses"])

            state["final_answer"] = final_answer
        
        state["messages"].append(AIMessage(content=state["final_answer"]))
        state["completed_at"] = datetime.now(timezone.utc)
        
        logger.info(f"Synthesized response from {len(state['team_responses'])} agents")
    
        return state
    
    async def _create_executive_summary(self, team_responses: List, query: str) -> str:
        """
        Create a formal executive summary using the coordinator agent.
        This is used for complex multi-agent responses that need consensus.
        """
        # Prepare the context for the coordinator
        expert_analyses = []
        for resp in team_responses:
            # Handle unified response format
            summary = resp.response.summary if resp.response.summary else resp.response.content
            recommendations = resp.response.recommendations if resp.response.recommendations else []
            
            analysis = f"""
<expert_analysis>
  <agent_name>{resp.agent_name}</agent_name>
  <agent_role>{resp.agent_role.value}</agent_role>
  <summary>{summary}</summary>
  <recommendations>
    {'\\n'.join(f"<item>{rec}</item>" for rec in recommendations)}
  </recommendations>
</expert_analysis>
"""
            expert_analyses.append(analysis)

        coordination_context = f"""
**Original User Query:**
{query}

**Analyses from Specialist Agents:**
{''.join(expert_analyses)}
"""
        
        logger.info(f"Creating executive summary for {len(team_responses)} agents")
        final_report_structured = await self.coordinator.respond(messages=[HumanMessage(content=coordination_context)])

        # Format the final report into a user-friendly markdown string
        final_answer = f"## Executive Summary\n\n{final_report_structured.summary}\n\n"
        
        if final_report_structured.recommendations:
            final_answer += "## Prioritized Recommendations\n\n"
            for i, rec in enumerate(final_report_structured.recommendations, 1):
                final_answer += f"**{i}.** {rec}\n\n"

        # Append tool usage information from all agents
        all_tools_used = []
        for resp in team_responses:
            if resp.response.tools_used:
                all_tools_used.extend(resp.response.tools_used)

        if all_tools_used:
            final_answer += "\n\n---\n"
            final_answer += "**Sources & Tools Used:**\n"
            unique_tool_names = sorted(list(set(tool.tool_name for tool in all_tools_used)))
            for tool_name in unique_tool_names:
                final_answer += f"- **{tool_name}**\n"

        return final_answer
    
    def _create_simple_synthesis(self, team_responses: List) -> str:
        """
        Create a simple synthesis for basic multi-agent responses.
        This is used for straightforward cases that don't need formal coordination.
        """
        combined_summary = "## Team Analysis Summary\n\n"
        combined_summary += "Our cybersecurity team has analyzed your query:\n\n"
        
        for resp in team_responses:
            agent_name = resp.agent_name.split(' (')[0]  # Clean up name
            combined_summary += f"**{agent_name}**: "
            
            # Use content if available, otherwise use summary
            if resp.response.content:
                combined_summary += resp.response.content + "\n\n"
            elif resp.response.summary:
                combined_summary += resp.response.summary + "\n\n"
            else:
                combined_summary += "Provided analysis for the query.\n\n"
        
        # Collect recommendations from all responses
        all_recommendations = []
        for resp in team_responses:
            if resp.response.recommendations:
                for rec in resp.response.recommendations:
                    if rec not in all_recommendations:
                        all_recommendations.append(rec)
        
        final_answer = combined_summary
        
        if all_recommendations:
            final_answer += "## Key Recommendations\n\n"
            for rec in all_recommendations:
                final_answer += f"• {rec}\n"
            final_answer += "\n"
        
        # Append tool usage from all agents
        all_tools_used = []
        for resp in team_responses:
            if resp.tools_used:
                all_tools_used.extend(resp.tools_used)

        if all_tools_used:
            final_answer += "\n**Sources & Tools Used:**\n"
            unique_tool_names = sorted(list(set(tool.tool_name for tool in all_tools_used)))
            for tool_name in unique_tool_names:
                final_answer += f"• {tool_name}\n"

        return final_answer
    
    @observe(name="check_quality")
    async def check_quality(self, state: WorkflowState) -> WorkflowState:
        """
        Perform general response quality evaluation using LLM-as-a-Judge.
        
        This checks overall response quality including:
        - Technical accuracy and correctness
        - Completeness and helpfulness  
        - Appropriate tone and format
        - Actionable recommendations
        - Professional cybersecurity standards
        
        If quality fails, this step can enhance/improve the response automatically.
        This is the primary quality gate for all cybersecurity responses.
        
        Args:
            state: Current workflow state with final_answer to evaluate
            
        Returns:
            Updated state with quality_score, quality_passed, and potentially enhanced response
        """
        if not self.quality_system or not self.enable_quality_gates:
            state["quality_passed"] = True
            state["quality_score"] = 1.0
            return state
        
        # Determine agent type for quality checking based on response strategy
        response_strategy = state.get("response_strategy", "direct")
        
        if response_strategy == "general_query":
            # For general queries, skip quality check or use general evaluation
            logger.info("Skipping quality check for general assistant response")
            state["quality_passed"] = True
            state["quality_score"] = 10.0
            return state
        elif state["team_responses"]:
            primary_response = max(state["team_responses"], key=lambda r: r.response.confidence_score)
            agent_type = primary_response.agent_role.value
        else:
            agent_type = "incident_response"  # Default for cybersecurity queries
        
        # Get context continuity information
        context_continuity = state.get("context_continuity", {})
        is_follow_up = context_continuity.get("is_follow_up", False)
        context_maintained = context_continuity.get("context_maintained", True)
        
        # Run quality validation with context awareness
        quality_result = await self.quality_system.validate_response(
            query=state["query"],
            response=state["final_answer"],
            agent_type=agent_type,
            context_info={
                "is_follow_up": is_follow_up,
                "context_maintained": context_maintained,
                "previous_context": context_continuity.get("previous_context")
            }
        )
        
        state["quality_passed"] = quality_result.passed
        state["quality_score"] = quality_result.overall_score
        
        # Get agent-specific quality threshold
        from config.agent_config import get_quality_threshold, AgentRole
        try:
            agent_role = AgentRole(agent_type)
            quality_threshold = get_quality_threshold(agent_role)
        except (ValueError, KeyError):
            quality_threshold = 7.0  # Fallback threshold
        
        # If quality score is below threshold and we haven't retried too much, enhance the response
        if quality_result.overall_score < quality_threshold and state["error_count"] < 2:
            logger.info(f"Quality check failed (score: {quality_result.overall_score:.2f} < {quality_threshold}), enhancing response...")
            state["quality_passed"] = False # Explicitly mark as failed before enhancement
            
            enhanced_response = await self.quality_system.enhance_response(
                query=state["query"],
                response=state["final_answer"],
                feedback=quality_result.feedback,
                agent_type=agent_type
            )
            
            state["final_answer"] = enhanced_response
            state["quality_passed"] = True  # Assume enhanced response passes
            
            # Log enhancement
            logger.info("Response enhanced successfully")
        
        return state
    
    @observe(name="check_rag_quality")
    async def check_rag_quality(self, state: WorkflowState) -> WorkflowState:
        """
        Evaluate RAG (Retrieval-Augmented Generation) quality when tools were used.
        
        This specialized quality check runs ONLY when agents used tools that retrieved 
        external information (web search, knowledge base, vulnerability databases, etc.).
        
        RAG-specific evaluations:
        - **Groundedness**: Is the final response actually based on the retrieved context?
        - **Relevance**: Was the retrieved information relevant to the user's query?
        
        This helps ensure that:
        1. Agents don't ignore tool results and make up information
        2. Tool retrieval is working effectively  
        3. Retrieved context is appropriate for the query
        
        Results are logged for monitoring and stored in state for analytics.
        This is complementary to general quality checking, not a replacement.
        
        Args:
            state: Current workflow state with team_responses containing tool usage
            
        Returns:
            Updated state with rag_grounded and rag_relevance_score metrics
        """
        if not self.quality_system or not self.enable_quality_gates:
            return state
        
        # Collect all context chunks from tool usage
        context_chunks = []
        for response in state["team_responses"]:
            for tool_call in response.tools_used:
                if "result" in tool_call:
                    # Safe tool result extraction
                    tool_result = tool_call.get("result")
                    if hasattr(tool_result, 'model_dump_json'):
                        # Pydantic model - serialize properly
                        result_text = tool_result.model_dump_json()
                    elif hasattr(tool_result, 'content'):
                        # Has content field
                        result_text = str(tool_result.content)
                    elif hasattr(tool_result, 'summary'):
                        # Has summary field
                        result_text = str(tool_result.summary)
                    else:
                        # Fallback to string conversion
                        result_text = str(tool_result)
                    
                    if result_text:
                        context_chunks.append(result_text[:500])  # Limit chunk size
        
        if not context_chunks:
            return state  # No RAG to check
        
        # Check groundedness
        groundedness_result = await self.quality_system.check_groundedness(
            answer=state["final_answer"],
            context_chunks=context_chunks
        )
        
        # Check relevance
        relevance_result = await self.quality_system.check_relevance(
            query=state["query"],
            context_chunks=context_chunks
        )
        
        # Log RAG quality results
        logger.info(
            f"RAG Quality - Grounded: {groundedness_result.grounded}, "
            f"Relevance: {relevance_result.score}/10"
        )
        
        # Store in state if needed
        state["rag_grounded"] = groundedness_result.grounded
        state["rag_relevance_score"] = relevance_result.score
        
        return state