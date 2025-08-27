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
from workflow.schemas import TeamResponse
from config.agent_config import AgentRole
from agents.factory import AgentFactory
from cybersec_mcp.cybersec_tools import CybersecurityToolkit


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

    @observe(name="analyze_query")
    async def analyze_query(self, state: WorkflowState) -> WorkflowState:
        """
        Analyze and classify the user query to determine context and routing strategy.
        
        This is the main analysis step where we:
        1. Understand what the user is asking for
        2. Classify if it's cybersecurity-related or general
        3. Determine the appropriate response strategy
        4. Set up routing information for the workflow
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with classification and routing decision
        """
        logger.info(f"🔍 Analyzing and classifying query: {state['query'][:100]}...")
        
        # Set metadata
        state["started_at"] = datetime.now(timezone.utc)
        state["messages"].append(HumanMessage(content=state["query"]))
        
        # Perform intelligent classification and routing decision
        routing_decision = await self.router.determine_routing_strategy(state["query"])
        
        # Update state with analysis results
        state["response_strategy"] = routing_decision.response_strategy
        state["agents_to_consult"] = routing_decision.relevant_agents
        state["estimated_complexity"] = routing_decision.estimated_complexity
        
        # Set first agent if any
        if routing_decision.relevant_agents:
            state["current_agent"] = routing_decision.relevant_agents[0]
            
        # Determine if consensus needed
        state["needs_consensus"] = len(routing_decision.relevant_agents) > 1
        
        logger.info(f"✅ Analysis complete for '{state['query'][:50]}...': {routing_decision.response_strategy} "
                   f"(complexity: {routing_decision.estimated_complexity}) - {routing_decision.reasoning}")
        
        return state

    @observe(name="check_context_continuity")
    async def check_context_continuity(self, state: WorkflowState) -> WorkflowState:
        """
        Check if the current query maintains cybersecurity conversation context.
        
        This node analyzes whether the current query is a follow-up to a previous
        cybersecurity conversation and maintains the appropriate context.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with context continuity information
        """
        logger.info(f"🔗 Checking context continuity for query: {state['query'][:100]}...")
        
        # Get conversation history from state
        conversation_history = state.get("conversation_history", [])
        
        if not conversation_history:
            # First query in conversation, no context to maintain
            state["context_continuity"] = {
                "is_follow_up": False,
                "context_maintained": True,
                "previous_context": None,
                "confidence": 1.0,
                "reasoning": "First query in conversation"
            }
            logger.info("✅ First query in conversation - no context to maintain")
            return state
        
        # Analyze the last few messages for cybersecurity context
        recent_messages = conversation_history[-3:]  # Last 3 messages for context
        
        # Create context analysis prompt
        context_prompt = f"""
        Analyze whether the current query maintains cybersecurity conversation context.
        
        **Recent Conversation History:**
        {chr(10).join([f"- {msg.get('role', 'user')}: {msg.get('content', '')[:200]}..." for msg in recent_messages])}
        
        **Current Query:**
        {state['query']}
        
        **Instructions:**
        1. Determine if this is a follow-up to a previous cybersecurity conversation
        2. Assess if the cybersecurity context is maintained
        3. Provide confidence level and reasoning
        
        Respond in JSON format:
        {{
            "is_follow_up": <boolean>,
            "context_maintained": <boolean>,
            "previous_context": "<brief summary of previous cybersecurity context>",
            "confidence": <float between 0-1>,
            "reasoning": "<explanation of the assessment>"
        }}
        """
        
        try:
            # Use the LLM to analyze context continuity
            response = await self.llm_client.ainvoke([
                SystemMessage(content="You are an expert at analyzing conversation context and continuity."),
                HumanMessage(content=context_prompt)
            ])
            
            # Parse the response
            import json
            context_result = json.loads(response.content)
            
            state["context_continuity"] = context_result
            
            logger.info(f"✅ Context continuity check: Follow-up={context_result['is_follow_up']}, "
                       f"Context maintained={context_result['context_maintained']}, "
                       f"Confidence={context_result['confidence']:.2f}")
            
        except Exception as e:
            logger.warning(f"Failed to analyze context continuity: {e}")
            # Default to assuming context is maintained
            state["context_continuity"] = {
                "is_follow_up": True,
                "context_maintained": True,
                "previous_context": "Previous cybersecurity conversation",
                "confidence": 0.7,
                "reasoning": "Default assumption due to analysis failure"
            }
        
        return state
    
    # Removed redundant triage_query - analysis now handles classification and routing decision

    @observe(name="consult_agent")
    async def consult_agent(self, state: WorkflowState) -> WorkflowState:
        """
        Consults all agents in the agents_to_consult list for their expertise.

        Args:
            state: Current workflow state containing agents_to_consult and messages.

        Returns:
            Updated state with team responses from all consulted agents.
        """
        agents_to_consult = state["agents_to_consult"]
        messages = state["messages"]
        
        # Consult each agent in the list
        for agent_role in agents_to_consult:
            agent = self.agents.get(agent_role)
            if not agent:
                error_msg = f"Agent {agent_role} not found"
                logger.error(error_msg)
                continue

            try:
                logger.info(f"Consulting {agent.name}...")
                structured_response = await agent.respond(messages=messages)
                
                team_response = TeamResponse(
                    agent_name=agent.name,
                    agent_role=agent_role,
                    response=structured_response,
                    tools_used=structured_response.tools_used,
                )
                
                state["team_responses"].append(team_response)
                logger.info(f"{agent.name} provided response (confidence: {structured_response.confidence_score:.2f})")

            except Exception as e:
                logger.error(f"Error consulting {agent.name}: {e}")
                state["error_count"] = state.get("error_count", 0) + 1
                state["last_error"] = str(e)
                continue
        
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
        logger.info(f"🤖 General assistant handling query: {state['query'][:50]}...")
        
        try:
            # Use shared LLM client
            llm = self.llm_client
            
            # Bind the web search tool to the LLM  
            llm_with_tools = llm.bind_tools([self.web_search_tool])
            
            # System prompt for general assistant with web search
            system_prompt = """
You are a helpful, friendly general assistant with web search capabilities.

- Be warm, helpful, and direct
- For greetings, respond as a friendly human would
- For questions requiring current information (weather, news, recent events, current facts), use the web_search_tool
- For general knowledge questions, answer directly if you're confident
- Keep responses concise but complete
- Be engaging and personable

When to use web search:
- Weather queries ("What's the weather in London?")
- Current news or events
- Recent information that might have changed
- Facts that need to be up-to-date
- Any topic where current/real-time information is important

The web_search_tool is now generic and works for any type of query - you control the focus through your search terms.
"""
            
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
                        # Handle web search tool specifically (since we have the instance)
                        if tool_name == "web_search":  # Note: direct tool name, not wrapper
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
                final_answer = final_response.content
            else:
                # No tools used, use direct response
                final_answer = response.content
            
            state["final_answer"] = final_answer
            state["messages"].append(AIMessage(content=final_answer))
            state["completed_at"] = datetime.now(timezone.utc)
            
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
        logger.info(f"🎯 Handling simple cybersecurity query directly: {state['query'][:50]}...")
        
        try:
            # Handle direct cybersecurity response with router tools
            final_answer = await self.router.direct_response(state["query"])
            
            state["final_answer"] = final_answer
            
            # Add to conversation
            state["messages"].append(AIMessage(content=state["final_answer"]))
            state["completed_at"] = datetime.now(timezone.utc)
            
            logger.info("Direct cybersecurity response completed successfully")
            
        except Exception as e:
            logger.error(f"Direct response failed: {e}")
            state["final_answer"] = f"I encountered an error while processing your cybersecurity query: {str(e)}"
            state["error_count"] = state.get("error_count", 0) + 1
            state["last_error"] = str(e)
        
        return state

    def get_team_response_as_str(self, team_response: TeamResponse) -> str:
        """A simple node to extract the string content from a TeamResponse object."""
        return f"**{team_response.agent_name} ({team_response.agent_role.value}):**\n{team_response.response.summary}"

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

        # The coordinator returns a StructuredAgentResponse, but its content is a FinalReport
        # We need to adjust the base agent to handle this, or cast the response here.
        # For now, let's assume the response can be cast or handled appropriately.
        final_report_structured = await self.coordinator.respond(messages=[{"role": "user", "content": coordination_context}])

        # Format the final report into a user-friendly markdown string
        final_answer = f"## Executive Summary\n\n{final_report_structured.summary}\n\n"
        
        # This part needs adjustment based on how FinalReport is returned
        # Assuming summary contains the exec summary and recommendations the prioritized list
        if final_report_structured.recommendations:
            final_answer += "## Prioritized Recommendations\n\n"
            for i, rec in enumerate(final_report_structured.recommendations, 1):
                final_answer += f"**{i}.** {rec}\n\n"

        state["final_answer"] = final_answer
        state["messages"].append(AIMessage(content=state["final_answer"]))
        state["completed_at"] = datetime.now(timezone.utc)
        
        logger.info(f"Coordinator synthesized response from {len(state['team_responses'])} agents.")
        return state

    @observe(name="synthesize_responses")
    async def synthesize_responses(self, state: WorkflowState) -> WorkflowState:
        """
        Synthesize all agent responses into a final, high-quality answer.
        For single-agent responses, it rewrites them into a more natural, conversational format.
        For multi-agent responses, it combines them into a consolidated view.
        """
        if not state["team_responses"]:
            state["final_answer"] = "I couldn't gather expert analysis for your query."
            return state
        
        if len(state["team_responses"]) == 1:
            # For a single agent, rewrite the structured response into a natural, conversational format
            agent_response = state["team_responses"][0]
            summary = agent_response.response.summary
            recommendations = agent_response.response.recommendations
            
            synthesis_prompt = f"""
You are an expert at communicating cybersecurity advice. Your task is to rewrite the following structured analysis from a specialist into a single, cohesive, and easy-to-read response for the end-user.

**Use markdown formatting for better readability.** Structure your response with clear headers, bullet points, and emphasis where appropriate. Make it easy to scan and understand.

**Specialist's Analysis:**
---
**Summary:**
{summary}

**Recommendations:**
{', '.join(recommendations)}
---

Rewrite the above analysis into a clear, well-formatted markdown response with appropriate headers, bullet points, and emphasis.
"""
            
            llm_response = await self.llm_client.ainvoke([HumanMessage(content=synthesis_prompt)])
            final_answer = llm_response.content
            state["final_answer"] = final_answer
        
        else:
            # For multiple agents, create a consolidated view with markdown formatting
            combined_summary = "## Team Analysis Summary\n\nBased on our team's analysis, here is a consolidated view:\n\n"
            combined_recommendations = []
            
            for resp in state["team_responses"]:
                combined_summary += f"### {resp.agent_name} ({resp.agent_role.value})\n\n"
                combined_summary += f"{resp.response.summary}\n\n"
                if resp.response.recommendations:
                    for rec in resp.response.recommendations:
                        # Avoid duplicate recommendations
                        if rec not in combined_recommendations:
                            combined_recommendations.append(rec)

            final_answer = f"{combined_summary}"
            if combined_recommendations:
                final_answer += "## Consolidated Recommendations\n\n"
                for rec in combined_recommendations:
                    final_answer += f"• **{rec}**\n\n"
            
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
                feedback=quality_result.feedback
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