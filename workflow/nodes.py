"""
Node functions for the workflow graph.
Integrated with your existing QualityGateSystem.
"""

import logging
from datetime import datetime, timezone
from langfuse import observe
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain_openai import ChatOpenAI
from workflow.state import WorkflowState
from workflow.schemas import TeamResponse, SearchIntentResult
from config.agent_config import AgentRole
from agents.factory import AgentFactory
from cybersec_mcp.cybersec_tools import CybersecurityToolkit
from workflow.schemas import ContextContinuityCheck


logger = logging.getLogger(__name__)


class WorkflowNodes:
    """
    Contains all node functions for the workflow graph.
    """
    
    def __init__(self, agent_factory: "AgentFactory", toolkit: CybersecurityToolkit, llm_client: ChatOpenAI, enable_quality_gates: bool = True):
        """
        Initialize with agent factory, toolkit, and other components.
        """
        self.agent_factory = agent_factory
        self.toolkit = toolkit
        self.llm_client = llm_client
        self.enable_quality_gates = enable_quality_gates
        
        # We can get agents and coordinator from the factory when needed
        self.agents = agent_factory.create_all_agents()
        self.coordinator = agent_factory.create_agent(AgentRole.COORDINATOR)
        
        # Initialize other components
        self.router = self.agent_factory.create_router()
        self.quality_system = self.agent_factory.create_quality_system()

        # Pre-initialize the web search tool
        self.web_search_tool = self.toolkit.get_tool_by_name("web_search")
        if not self.web_search_tool:
            logger.warning("Web search tool not found in toolkit. General responses may be limited.")
        else:
            logger.info("Web search tool pre-initialized for general assistant.")

        # Create structured LLM for search intent detection
        self.search_intent_llm = llm_client.with_structured_output(SearchIntentResult)

        # Create structured LLM for context continuity check, including retry logic
        self.context_continuity_llm = llm_client.with_structured_output(
            ContextContinuityCheck
        ).with_retry(stop_after_attempt=2)

    async def _detect_web_search_intent(self, query: str) -> dict:
        """
        Intelligent web search intent detection using both keywords and LLM analysis.
        Only focuses on WEB search - internal knowledge search is left to agent expertise.
        
        Returns:
            dict with web_search_required, intent_type, confidence, and reasoning
        """
        query_lower = query.lower()
        
        # Quick keyword check for obvious web search requests
        explicit_web_triggers = [
            "look up", "look it up", "search for", "check online", "search online", 
            "web search", "search the web", "google", "find online"
        ]
        
        # Temporal triggers that suggest need for current information
        temporal_triggers = [
            "latest", "recent", "current", "new", "emerging", "today", "this week",
            "this month", "2024", "2025", "now", "currently", "nowadays"
        ]
        
        # Quick positive detection for explicit requests
        explicit_web_match = any(trigger in query_lower for trigger in explicit_web_triggers)
        has_temporal_indicators = any(trigger in query_lower for trigger in temporal_triggers)
        
        if explicit_web_match:
            return {
                "web_search_required": True,
                "intent_type": "explicit_web_request",
                "confidence": 0.95,
                "reasoning": f"Explicit web search language detected",
                "trigger_phrase": next(trigger for trigger in explicit_web_triggers if trigger in query_lower)
            }
        
        # For temporal indicators or ambiguous cases, use LLM analysis
        if has_temporal_indicators or any(word in query_lower for word in ["trends", "updates", "news", "happening"]):
            try:
                llm_prompt = f"""
Analyze this query to determine if it requires web search for current/recent information.

Query: "{query}"

Consider:
1. Does this ask for current, recent, or latest information that changes frequently?
2. Does this require real-time or up-to-date data from the web?
3. Is this asking about trends, news, or current events?
4. Would the answer be different today vs 6 months ago?

Examples that NEED web search:
- "latest CVE vulnerabilities"
- "current threat landscape" 
- "recent data breaches"
- "new security tools in 2025"

Examples that DON'T need web search:
- "explain NIST framework"
- "incident response best practices"
- "how to configure firewall rules"

Respond with structured analysis of web search necessity.
"""
                
                intent_result = await self.search_intent_llm.ainvoke([
                    SystemMessage(content="You are an expert at determining when queries need current web information vs existing knowledge."),
                    HumanMessage(content=llm_prompt)
                ])
                
                return {
                    "web_search_required": intent_result.needs_web_search,
                    "intent_type": "llm_analyzed" if intent_result.needs_web_search else "no_web_needed",
                    "confidence": intent_result.confidence,
                    "reasoning": intent_result.reasoning,
                    "trigger_phrase": None
                }
                
            except Exception as e:
                logger.warning(f"LLM search intent analysis failed: {e}")
                # Fallback: if has temporal indicators, assume web search needed
                return {
                    "web_search_required": has_temporal_indicators,
                    "intent_type": "temporal_fallback" if has_temporal_indicators else "no_web_needed",
                    "confidence": 0.7 if has_temporal_indicators else 0.9,
                    "reasoning": "Fallback analysis due to LLM error",
                    "trigger_phrase": None
                }
        
        # No web search intent detected
        return {
            "web_search_required": False,
            "intent_type": "no_web_needed",
            "confidence": 0.9,
            "reasoning": "No temporal indicators or explicit web search requests",
            "trigger_phrase": None
        }

    @observe(name="analyze_query")
    async def analyze_query(self, state: WorkflowState) -> WorkflowState:
        """
        Analyze and classify the user query - now simplified to focus on web search intent.
        Context-aware routing happens AFTER context continuity check.
        """
        logger.info(f"Analyzing query for web search intent: {state['query'][:100]}...")
        
        # Set metadata
        state["started_at"] = datetime.now(timezone.utc)
        state["messages"].append(HumanMessage(content=state["query"]))
        
        # DETECT WEB SEARCH INTENT (this is still useful for agents)
        web_search_intent = await self._detect_web_search_intent(state["query"])
        state["web_search_intent"] = web_search_intent
        
        if web_search_intent["web_search_required"]:
            logger.info(f"WEB SEARCH INTENT DETECTED: {web_search_intent['intent_type']} "
                       f"(confidence: {web_search_intent['confidence']:.2f}) - {web_search_intent['reasoning']}")
        
        logger.info(f"Analysis complete - web search intent recorded")
        
        return state

    @observe(name="check_context_continuity")
    async def check_context_continuity(self, state: WorkflowState) -> WorkflowState:
        """
        Check if the current query maintains cybersecurity conversation context
        AND perform context-aware routing.
        """
        logger.info(f"Checking context continuity for query: {state['query'][:100]}...")
        
        # DEBUG: Log all state information
        logger.info(f"DEBUG: Active agent in state: {state.get('active_agent')}")
        logger.info(f"DEBUG: Conversation context in state: {state.get('conversation_context')}")
        logger.info(f"DEBUG: Thread ID: {state.get('thread_id')}")
        
        conversation_history = state.get("conversation_history", [])
        logger.info(f"DEBUG: Conversation history length: {len(conversation_history)}")
        
        # If no conversation history, check if we have active_agent from previous state
        if not conversation_history:
            active_agent = state.get("active_agent")
            conversation_context = state.get("conversation_context")
            
            if active_agent and conversation_context == "cybersecurity":
                # We have an active cybersecurity agent from previous state
                logger.info(f"No conversation history, but found active agent: {active_agent}")
                state["context_continuity"] = {
                    "is_follow_up": True,
                    "context_maintained": True,
                    "previous_context": f"Previous conversation with {active_agent.value}",
                    "specialist_context": active_agent.value.lower(),
                    "confidence": 0.9,
                    "reasoning": f"Active agent {active_agent.value} found in persisted state"
                }
            else:
                logger.info("First query in conversation - no context to maintain")
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
            logger.info(f"DEBUG: Recent messages: {[msg.get('role') for msg in recent_messages]}")
            
            context_prompt = f"""
        Analyze whether the current query maintains cybersecurity conversation context and specialist expertise.

        **Recent Conversation History:**
        {chr(10).join([f"- {msg.get('role', 'user')}: {msg.get('content', '')[:200]}..." for msg in recent_messages])}

        **Current Query:**
        {state['query']}

        **Assessment Criteria:**
        1. Is this a follow-up to a previous cybersecurity conversation?
        2. Does it maintain the specialized context (incident response, threat analysis, compliance, etc.)?
        3. Would a cybersecurity specialist need to provide expertise for this query?
        4. Does the query build on previous security analysis or recommendations?
        """
            
            try:
                context_result = await self.context_continuity_llm.ainvoke([
                    SystemMessage(content="You are an expert at analyzing cybersecurity conversation context and specialist expertise continuity."),
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
        """
        Consults all agents in the agents_to_consult list for their expertise.
        Now tracks the active agent for persistent conversations.
        """
        agents_to_consult = state["agents_to_consult"]
        messages = state["messages"]
        
        # Get web search intent
        web_search_intent = state.get("web_search_intent", {})
        
        # Consult each agent in the list
        for agent_role in agents_to_consult:
            agent = self.agents.get(agent_role)
            if not agent:
                error_msg = f"Agent {agent_role} not found"
                logger.error(error_msg)
                continue

            try:
                logger.info(f"CONSULTING: {agent.name}")
                logger.info(f"{agent.name}: {len(agent.permitted_tools)} tools available: {[tool.name for tool in agent.permitted_tools]}")
                logger.info(f"{agent.name}: Processing {len(messages)} messages in conversation history")
                logger.info(f"{agent.name}: Current query: '{state['query'][:100]}...'")
                
                # The user's query should remain pristine. Context is passed as a separate message.
                messages_for_agent = [HumanMessage(content=state['query'])]

                if web_search_intent.get("web_search_required"):
                    logger.info(f"WEB SEARCH CONTEXT: {agent.name} - {web_search_intent['intent_type']} "
                              f"(confidence: {web_search_intent['confidence']:.2f})")
                    
                    # Create a system message with the search context
                    search_context = f"[SEARCH CONTEXT: Your analysis indicates the user's query may require current information from the web. "
                    if web_search_intent['intent_type'] == 'explicit_web_request':
                        search_context += f"This was detected from an explicit request ('{web_search_intent.get('trigger_phrase', 'web search')}'). "
                    else:
                        search_context += f"This was detected based on temporal indicators or currency requirements. "
                    search_content = search_context + f"Reasoning: {web_search_intent['reasoning']}. You should strongly consider using the web_search tool.]"
                    
                    # Add the context as a separate message for the agent
                    messages_for_agent.insert(0, SystemMessage(content=search_content))

                logger.info(f"{agent.name}: Using only current query, not conversation history")
                structured_response = await agent.respond(messages=messages_for_agent)
                
                team_response = TeamResponse(
                    agent_name=agent.name,
                    agent_role=agent_role,
                    response=structured_response,
                    tools_used=structured_response.tools_used,
                )
                
                state["team_responses"].append(team_response)
                
                # Log tool usage
                if structured_response.tools_used:
                    tool_names = [tool.tool_name for tool in structured_response.tools_used]
                    logger.info(f"{agent.name}: Used tools: {', '.join(tool_names)}")
                else:
                    logger.warning(f"{agent.name}: NO TOOLS USED")
                
                logger.info(f"{agent.name}: Response completed (confidence: {structured_response.confidence_score:.2f})")

            except Exception as e:
                logger.error(f"Error consulting {agent.name}: {e}")
                state["error_count"] = state.get("error_count", 0) + 1
                state["last_error"] = str(e)
                continue
        
        # Track the active agent for follow-ups (agent persistence)
        if len(state["team_responses"]) == 1:
            # Single agent response - track this agent as active
            state["active_agent"] = state["team_responses"][0].agent_role
            state["conversation_context"] = "cybersecurity"
            logger.info(f"Tracking active agent for follow-ups: {state['active_agent'].value}")
        elif len(state["team_responses"]) > 1:
            # Multi-agent response - don't set a single active agent
            state["active_agent"] = None
            state["conversation_context"] = "cybersecurity"
            logger.info("Multi-agent response - no single active agent set")
        
        return state

    @observe(name="general_response")
    async def general_response(self, state: WorkflowState) -> WorkflowState:
        """
        Handle general (non-cybersecurity) queries with web search capabilities.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with general assistant response
        """
        logger.info(f"--- Entering General Response Node ---")
        logger.info(f"State 'query' at this point: '{state['query']}'")
        logger.info(f"Number of messages in state: {len(state['messages'])}")
        if state['messages']:
            logger.info(f"Last message content: '{state['messages'][-1].content}'")
            
        logger.info(f"General assistant handling query: {state['query'][:50]}...")
        
        try:
            # Use shared LLM client
            llm = self.llm_client
            
            # Bind the web search tool to the LLM  
            llm_with_tools = llm.bind_tools([self.web_search_tool])
            
            # System prompt for general assistant with web search
            system_prompt = """
You are a helpful, friendly general assistant with web search capabilities.

- Be warm, helpful, and direct.
- For greetings, respond as a friendly human would.
- **You MUST use the `web_search_tool` for any questions about the current time, date, weather, or any other real-time information. Do not answer from your own knowledge.**
- For questions requiring current information (weather, news, recent events, current facts), use the web_search_tool.
- For general knowledge questions, answer directly if you're confident.
- Keep responses concise but complete.
- Be engaging and personable.

When to use web search:
- **Current time or date queries.**
- Weather queries ("What's the weather in London?")
- Current news or events
- Recent information that might have changed
- Facts that need to be up-to-date
- Any topic where current/real-time information is important

The web_search_tool is now generic and works for any type of query - you control the focus through your search terms.
"""
            
            # Use the full message history for context-awareness
            messages = [
                SystemMessage(content=system_prompt),
                *state["messages"]
            ]
            
            # First LLM call - let it decide to use tools or not
            response = await llm_with_tools.ainvoke(messages)
            
            # Handle tool calls if any
            if hasattr(response, 'tool_calls') and response.tool_calls:
                logger.info(f"General assistant making {len(response.tool_calls)} tool calls")
                messages.append(response)
                
                # Execute tool calls
                for tool_call in response.tool_calls:
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]
                    tool_id = tool_call["id"]
                    
                    try:
                        if tool_name == "web_search":
                            logger.info(f"LLM generated tool query for web_search: '{tool_args.get('query')}'")
                            tool_result = await self.web_search_tool.ainvoke(tool_args)
                        else:
                            # For any other tools that might be called
                            tool_result = f"Tool {tool_name} executed successfully"
                        
                        messages.append(ToolMessage(
                            content=str(tool_result),
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

    @observe(name="coordinate_responses")
    async def coordinate_responses(self, state: WorkflowState) -> WorkflowState:
        """
        Invokes the CoordinatorAgent to synthesize a final report.
        """
        if not state["team_responses"]:
            state["final_answer"] = "I couldn't gather expert analysis for your query."
            return state

        # Prepare the context for the coordinator
        expert_analyses = []
        for resp in state["team_responses"]:
            analysis = f"""
<expert_analysis>
  <agent_name>{resp.agent_name}</agent_name>
  <agent_role>{resp.agent_role.value}</agent_role>
  <summary>{resp.response.summary}</summary>
  <recommendations>
    {'\\n'.join(f"<item>{rec}</item>" for rec in resp.response.recommendations)}
  </recommendations>
</expert_analysis>
"""
            expert_analyses.append(analysis)

        coordination_context = f"""
**Original User Query:**
{state['query']}

**Analyses from Specialist Agents:**
{''.join(expert_analyses)}
"""
        
        logger.info(f"COORDINATOR: Context length: {len(coordination_context)} chars")
        logger.info(f"COORDINATOR: Agent responses to synthesize: {[resp.agent_name for resp in state['team_responses']]}")

        logger.info(f"COORDINATOR: Processing {len(state['team_responses'])} agent responses")
        final_report_structured = await self.coordinator.respond(messages=[HumanMessage(content=coordination_context)])

        # Format the final report into a user-friendly markdown string
        final_answer = f"## Executive Summary\n\n{final_report_structured.summary}\n\n"
        
        if final_report_structured.recommendations:
            final_answer += "## Prioritized Recommendations\n\n"
            for i, rec in enumerate(final_report_structured.recommendations, 1):
                final_answer += f"**{i}.** {rec}\n\n"

        # Append tool usage information from all agents
        all_tools_used = []
        for resp in state["team_responses"]:
            if resp.response.tools_used:
                all_tools_used.extend(resp.response.tools_used)

        if all_tools_used:
            final_answer += "\n\n---\n"
            final_answer += "**Sources & Tools Used:**\n"
            unique_tool_names = sorted(list(set(tool.tool_name for tool in all_tools_used)))
            for tool_name in unique_tool_names:
                final_answer += f"- **{tool_name}**\n"

        state["final_answer"] = final_answer
        state["messages"].append(AIMessage(content=state["final_answer"]))
        state["completed_at"] = datetime.now(timezone.utc)
        
        # For coordinated responses, don't set a single active agent
        state["active_agent"] = None
        state["conversation_context"] = "cybersecurity"
        
        logger.info(f"COORDINATOR: Synthesized response from {len(state['team_responses'])} agents")
        logger.info(f"COORDINATOR: Final response length: {len(state['final_answer'])} chars")
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
            # For single agent with natural response, use it directly with light formatting
            agent_response = state["team_responses"][0]
            response_content = agent_response.response
            
            # Handle both natural and structured responses
            if hasattr(response_content, 'content'):
                # Natural response - use directly
                final_answer = response_content.content
            else:
                # Structured response - format naturally
                final_answer = response_content.summary
                if response_content.recommendations:
                    final_answer += "\n\n**Key Recommendations:**\n"
                    for rec in response_content.recommendations:
                        final_answer += f"• {rec}\n"

            # Append tool usage information if any tools were used
            if agent_response.tools_used:
                final_answer += "\n\n**Sources & Tools Used:**\n"
                for tool in agent_response.tools_used:
                    final_answer += f"• {tool.tool_name}\n"

            state["final_answer"] = final_answer
        
        else:
            # For multiple agents, create a structured consolidated view
            combined_summary = "## Team Analysis Summary\n\n"
            combined_summary += "Our cybersecurity team has analyzed your query:\n\n"
            
            for resp in state["team_responses"]:
                agent_name = resp.agent_name.split(' (')[0]  # Clean up name
                combined_summary += f"**{agent_name}**: "
                
                # Handle both response types
                if hasattr(resp.response, 'content'):
                    combined_summary += resp.response.content + "\n\n"
                else:
                    combined_summary += resp.response.summary + "\n\n"
            
            # Collect recommendations from structured responses
            all_recommendations = []
            for resp in state["team_responses"]:
                if hasattr(resp.response, 'recommendations') and resp.response.recommendations:
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
            for resp in state["team_responses"]:
                if resp.tools_used:
                    all_tools_used.extend(resp.tools_used)

            if all_tools_used:
                final_answer += "\n**Sources & Tools Used:**\n"
                unique_tool_names = sorted(list(set(tool.tool_name for tool in all_tools_used)))
                for tool_name in unique_tool_names:
                    final_answer += f"• {tool_name}\n"

            state["final_answer"] = final_answer
        
        state["messages"].append(AIMessage(content=state["final_answer"]))
        state["completed_at"] = datetime.now(timezone.utc)
        
        logger.info(f"Synthesized response from {len(state['team_responses'])} agents")
    
        return state
    
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
                    # Extract text from tool results
                    result_text = str(tool_call["result"])
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