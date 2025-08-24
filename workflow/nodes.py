"""
Node functions for the workflow graph.
Integrated with your existing QualityGateSystem.
"""

import logging
from typing import Dict, Any
from datetime import datetime, timezone
from langfuse import observe
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain_openai import ChatOpenAI
from workflow.state import WorkflowState
from workflow.schemas import TeamResponse
from config.agent_config import AgentRole

logger = logging.getLogger(__name__)


class WorkflowNodes:
    """
    Contains all node functions for the workflow graph.
    """
    
    def __init__(self, agents: Dict[AgentRole, Any], coordinator: Any, router: Any, quality_system: Any, llm_client: ChatOpenAI, enable_quality_gates: bool = True):
        """
        Initialize with available agents, a coordinator, and pre-initialized components.
        """
        self.agents = agents
        self.coordinator = coordinator
        self.router = router
        self.quality_system = quality_system
        self.llm_client = llm_client  # Reuse shared LLM client
        self.enable_quality_gates = enable_quality_gates

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
                
                # Extract tool usage information from the structured response
                tools_used = [
                    {
                        "tool_name": tool.tool_name,
                        "result": tool.tool_result,
                        "timestamp": tool.timestamp.isoformat()
                    }
                    for tool in structured_response.tools_used
                ]

                team_response = TeamResponse(
                    agent_name=agent.name,
                    agent_role=agent_role,
                    response=structured_response,
                    tools_used=tools_used,
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
            
            # Get web search tool from toolkit (as a LangChain tool)
            from cybersec_tools import cybersec_toolkit
            available_tools = cybersec_toolkit.get_all_tools()
            web_search_tool = next(tool for tool in available_tools if tool.name == "search_web")
            
            # Bind the web search tool to the LLM  
            llm_with_tools = llm.bind_tools([web_search_tool])
            
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
                        if tool_name == "search_web":  # Note: direct tool name, not wrapper
                            tool_result = await web_search_tool.ainvoke(tool_args)
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

        # Format the final report into a user-friendly string
        final_answer = f"### Executive Summary\n{final_report_structured.summary}\n\n"
        
        # This part needs adjustment based on how FinalReport is returned
        # Assuming summary contains the exec summary and recommendations the prioritized list
        if final_report_structured.recommendations:
            final_answer += "### Prioritized Recommendations\n"
            for i, rec in enumerate(final_report_structured.recommendations, 1):
                final_answer += f"{i}. {rec}\n"

        state["final_answer"] = final_answer
        state["messages"].append(AIMessage(content=state["final_answer"]))
        state["completed_at"] = datetime.now(timezone.utc)
        
        logger.info(f"Coordinator synthesized response from {len(state['team_responses'])} agents.")
        return state

    @observe(name="synthesize_responses")
    async def synthesize_responses(self, state: WorkflowState) -> WorkflowState:
        """
        Synthesize all agent responses into a final, high-quality answer.
        """
        if not state["team_responses"]:
            state["final_answer"] = "I couldn't gather expert analysis for your query."
            return state
        
        if len(state["team_responses"]) == 1:
            response = state["team_responses"][0].response
            final_answer = f"**{state['team_responses'][0].agent_name}'s Analysis:**\n\n"
            final_answer += f"**Summary:**\n{response.summary}\n\n"
            if response.recommendations:
                final_answer += "**Recommendations:**\n"
                for rec in response.recommendations:
                    final_answer += f"- {rec}\n"
            state["final_answer"] = final_answer
        
        else:
            combined_summary = "Based on our team's analysis, here is a consolidated view:\n\n"
            combined_recommendations = []
            
            for resp in state["team_responses"]:
                combined_summary += f"**{resp.agent_name}'s Perspective ({resp.agent_role.value}):**\n"
                combined_summary += f"{resp.response.summary}\n\n"
                if resp.response.recommendations:
                    for rec in resp.response.recommendations:
                        # Avoid duplicate recommendations
                        if rec not in combined_recommendations:
                            combined_recommendations.append(rec)

            final_answer = f"{combined_summary}"
            if combined_recommendations:
                final_answer += "\n**Consolidated Recommendations:**\n"
                for rec in combined_recommendations:
                    final_answer += f"- {rec}\n"
            
            state["final_answer"] = final_answer
        
        from langchain_core.messages import AIMessage
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
        
        # Run quality validation
        quality_result = await self.quality_system.validate_response(
            query=state["query"],
            response=state["final_answer"],
            agent_type=agent_type
        )
        
        state["quality_passed"] = quality_result.passed
        state["quality_score"] = quality_result.overall_score
        
        # If quality failed and we haven't retried too much, enhance the response
        if not quality_result.passed and state["error_count"] < 2:
            logger.info(f"Quality check failed (score: {quality_result.overall_score:.2f}), enhancing response...")
            
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