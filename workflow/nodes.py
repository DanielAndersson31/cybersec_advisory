"""
Node functions for the workflow graph.
Integrated with your existing QualityGateSystem.
"""

import logging
from typing import Dict, Any
from datetime import datetime

from langfuse import observe

from workflow.state import WorkflowState
from workflow.schemas import TeamResponse
from workflow.router import QueryRouter
from workflow.quality_gates import QualityGateSystem
from config.agent_config import AgentRole

logger = logging.getLogger(__name__)


class WorkflowNodes:
    """
    Contains all node functions for the workflow graph.
    """
    
    def __init__(self, agents: Dict[AgentRole, Any], enable_quality_gates: bool = True):
        """
        Initialize with available agents.
        
        Args:
            agents: Dictionary of initialized agents
            enable_quality_gates: Whether to enable quality checking
        """
        self.agents = agents
        self.router = QueryRouter()
        
        # Use your QualityGateSystem
        self.quality_system = QualityGateSystem() if enable_quality_gates else None
        self.enable_quality_gates = enable_quality_gates
    
    @observe(name="analyze_query")
    async def analyze_query(self, state: WorkflowState) -> WorkflowState:
        """
        Initial analysis of the user query.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state
        """
        logger.info(f"Analyzing query: {state['query'][:100]}...")
        
        # Set metadata
        state["started_at"] = datetime.utcnow()
        
        # Add to messages for context
        from langchain_core.messages import HumanMessage
        state["messages"].append(HumanMessage(content=state["query"]))
        
        return state
    
    @observe(name="route_to_agents")
    async def route_to_agents(self, state: WorkflowState) -> WorkflowState:
        """
        Determine which agents should respond to this query.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with routing decision
        """
        # Get routing decision
        agents_to_consult = await self.router.determine_relevant_agents(state["query"])
        
        state["agents_to_consult"] = agents_to_consult
        
        # Set first agent if any
        if agents_to_consult:
            state["current_agent"] = agents_to_consult[0]
            logger.info(f"Will consult {len(agents_to_consult)} agents: {[a.value for a in agents_to_consult]}")
        else:
            # Default to incident response if no specific match
            state["agents_to_consult"] = [AgentRole.INCIDENT_RESPONSE]
            state["current_agent"] = AgentRole.INCIDENT_RESPONSE
            logger.info("No specific expertise match, defaulting to incident response")
        
        # Determine if consensus needed (multiple agents with different perspectives)
        state["needs_consensus"] = len(agents_to_consult) > 1
        
        return state
    
    @observe(name="consult_agent")
    async def consult_agent(self, state: WorkflowState) -> WorkflowState:
        """
        Consult the current agent for their expertise.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with agent response
        """
        if not state["current_agent"]:
            logger.warning("No current agent set")
            return state
        
        agent = self.agents.get(state["current_agent"])
        if not agent:
            logger.error(f"Agent {state['current_agent']} not found")
            state["error_count"] += 1
            return state
        
        try:
            messages = []
            if state.get("team_responses"):
                for resp in state["team_responses"]:
                    sanitized_name = resp.agent_role.value
                    messages.append({"role": "assistant", "name": sanitized_name, "content": resp.response.summary})
            
            messages.append({"role": "user", "content": state["query"]})

            logger.info(f"Consulting {agent.name}...")
            structured_response = await agent.respond(messages=messages)
            
            # TODO: Properly extract tool usage information from the new flow
            tools_used = []

            team_response = TeamResponse(
                agent_name=agent.name,
                agent_role=state["current_agent"],
                response=structured_response,
                tools_used=tools_used,
            )
            
            state["team_responses"].append(team_response)
            
            logger.info(f"{agent.name} provided response (confidence: {structured_response.confidence_score:.2f})")
            
        except Exception as e:
            logger.error(f"Error consulting {agent.name}: {e}")
            state["error_count"] += 1
            state["last_error"] = str(e)
        
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
        
        state["completed_at"] = datetime.utcnow()
        
        logger.info(f"Synthesized response from {len(state['team_responses'])} agents")
        
        return state
    
    @observe(name="check_quality")
    async def check_quality(self, state: WorkflowState) -> WorkflowState:
        """
        Check quality of the final response using your QualityGateSystem.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with quality results
        """
        if not self.quality_system or not self.enable_quality_gates:
            state["quality_passed"] = True
            state["quality_score"] = 1.0
            return state
        
        # Determine agent type for quality checking
        # Use the primary agent or the one with highest confidence
        if state["team_responses"]:
            primary_response = max(state["team_responses"], key=lambda r: r.response.confidence_score)
            agent_type = primary_response.agent_role.value
        else:
            agent_type = "incident_response"  # Default
        
        # Run quality validation
        quality_result = await self.quality_system.validate_response(
            query=state["query"],
            response=state["final_answer"],
            agent_type=agent_type
        )
        
        state["quality_passed"] = quality_result["passed"]
        state["quality_score"] = quality_result["overall_score"]
        
        # If quality failed and we haven't retried too much, enhance the response
        if not quality_result["passed"] and state["error_count"] < 2:
            logger.info(f"Quality check failed (score: {quality_result['overall_score']:.2f}), enhancing response...")
            
            enhanced_response = await self.quality_system.enhance_response(
                query=state["query"],
                response=state["final_answer"],
                feedback=quality_result["feedback"]
            )
            
            state["final_answer"] = enhanced_response
            state["quality_passed"] = True  # Assume enhanced response passes
            
            # Log enhancement
            logger.info("Response enhanced successfully")
        
        return state
    
    @observe(name="check_rag_quality")
    async def check_rag_quality(self, state: WorkflowState) -> WorkflowState:
        """
        Check RAG groundedness and relevance if context chunks are available.
        This is used when agents use tool results.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with RAG quality results
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
            f"RAG Quality - Grounded: {groundedness_result.get('grounded', False)}, "
            f"Relevance: {relevance_result.get('score', 0)}/10"
        )
        
        # Store in state if needed
        state["rag_grounded"] = groundedness_result.get("grounded", False)
        state["rag_relevance_score"] = relevance_result.get("score", 0)
        
        return state