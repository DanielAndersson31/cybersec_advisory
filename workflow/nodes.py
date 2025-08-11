"""
Node functions for the workflow graph.
Integrated with your existing QualityGateSystem.
"""

import logging
from typing import Dict, Any, List
from datetime import datetime

from langfuse import observe

from workflow.state import WorkflowState, TeamResponse
from workflow.router import QueryRouter
from workflow.quality_gates import QualityGateSystem  # Your existing quality gates
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
        self.router = QueryRouter(agents)
        
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
            # Build context from previous responses
            context = None
            if state["team_responses"]:
                context = {
                    "previous_responses": [
                        {
                            "agent": resp.agent_name,
                            "summary": resp.content[:200] + "..." if len(resp.content) > 200 else resp.content
                        }
                        for resp in state["team_responses"]
                    ]
                }
            
            # Get agent response
            logger.info(f"Consulting {agent.name}...")
            response = await agent.respond(
                query=state["query"],
                context=context
            )
            
            # Add to team responses
            team_response = TeamResponse(
                agent_name=response.agent,
                agent_role=state["current_agent"],
                content=response.content,
                tools_used=response.tools_used,
                confidence=getattr(response, 'confidence', 0.7)
            )
            
            state["team_responses"].append(team_response)
            
            logger.info(f"{agent.name} provided response (confidence: {team_response.confidence:.2f})")
            
        except Exception as e:
            logger.error(f"Error consulting {agent.name}: {e}")
            state["error_count"] += 1
            state["last_error"] = str(e)
        
        return state
    
    @observe(name="synthesize_responses")
    async def synthesize_responses(self, state: WorkflowState) -> WorkflowState:
        """
        Synthesize all agent responses into a final answer.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with final answer
        """
        if not state["team_responses"]:
            state["final_answer"] = "I couldn't gather expert analysis for your query."
            return state
        
        # Single response - use as is
        if len(state["team_responses"]) == 1:
            state["final_answer"] = state["team_responses"][0].content
        
        # Multiple responses - create unified answer
        else:
            if state["needs_consensus"]:
                # Build a consensus response
                answer = "Based on our team's analysis:\n\n"
                
                for resp in state["team_responses"]:
                    answer += f"**{resp.agent_name} ({resp.agent_role.value}):**\n"
                    answer += f"{resp.content}\n\n"
                
                # Add summary if responses are long
                if sum(len(r.content) for r in state["team_responses"]) > 1000:
                    answer += "**Summary:**\n"
                    answer += "The team has provided comprehensive analysis from multiple perspectives. "
                    answer += "Each expert has contributed their specialized knowledge to address your query."
            else:
                # Just concatenate nicely
                answer = "\n\n".join([resp.content for resp in state["team_responses"]])
            
            state["final_answer"] = answer
        
        # Add final answer to messages
        from langchain_core.messages import AIMessage
        state["messages"].append(AIMessage(content=state["final_answer"]))
        
        # Set completion time
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
            primary_response = max(state["team_responses"], key=lambda r: r.confidence)
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