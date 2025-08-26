"""
Main workflow graph for the cybersecurity team.
Orchestrates how agents collaborate to answer queries.
"""

import logging
from datetime import datetime, timezone
from typing import Literal, Optional

from langgraph.graph import StateGraph, END
from langfuse import observe
from langchain_core.messages import AIMessage

from workflow.state import WorkflowState
from workflow.nodes import WorkflowNodes
from workflow.fallbacks import ErrorHandler
from agents.factory import AgentFactory
from langchain_openai import ChatOpenAI
from config.settings import settings
from config.agent_config import AgentRole
from workflow.quality_gates import QualityGateSystem
from workflow.router import QueryRouter
from cybersec_mcp.cybersec_tools import CybersecurityToolkit


logger = logging.getLogger(__name__)


class CybersecurityTeamGraph:
    """
    Orchestrates the cybersecurity team workflow using LangGraph.
    """
    
    def __init__(self, enable_quality_checks: bool = True):
        """
        Initialize the team workflow.
        
        Args:
            enable_quality_checks: Whether to enable quality gates
        """
        # Create shared LLM client
        llm_client = ChatOpenAI(
            model=settings.default_model,
            temperature=0.1,
            max_tokens=4000
        )

        # Create all agents using the factory (much simpler now!)
        self.factory = AgentFactory(llm_client=llm_client)
        
        # Initialize workflow components
        self.toolkit = CybersecurityToolkit()
        self.nodes = WorkflowNodes(
            agent_factory=self.factory,
            toolkit=self.toolkit,
            llm_client=llm_client,
            enable_quality_gates=enable_quality_checks
        )
        self.error_handler = ErrorHandler()
        self.enable_quality_checks = enable_quality_checks
        
        # Build the graph
        self.graph = self._build_graph()
        
        # Don't compile yet - let conversation manager add checkpointer
        self.app = None
        self.checkpointer = None
        
        logger.info(f"Team workflow initialized with {len(self.agents)} agents")
    
    def compile_with_checkpointer(self, checkpointer):
        """
        Compile the graph with a specific checkpointer.
        This is called by the conversation manager.
        
        Args:
            checkpointer: LangGraph checkpointer (AsyncSqliteSaver or MemorySaver)
            
        Returns:
            Compiled app
        """
        self.checkpointer = checkpointer
        self.app = self.graph.compile(checkpointer=checkpointer)
        logger.info(f"Workflow compiled with {type(checkpointer).__name__}")
        return self.app
    
    def _build_graph(self) -> StateGraph:
        """
        Build the team collaboration graph with intelligent triage.
        
        Returns:
            Compiled state graph
        """
        workflow = StateGraph(WorkflowState)
        
        workflow.add_node("analyze", self.nodes.analyze_query)
        workflow.add_node("general_response", self.nodes.general_response)
        workflow.add_node("direct_response", self.nodes.direct_response)
        workflow.add_node("consult_agent", self.nodes.consult_agent)
        workflow.add_node("coordinate", self.nodes.coordinate_responses)
        
        # Add quality check if enabled
        if self.enable_quality_checks:
            workflow.add_node("quality", self.nodes.check_quality)
            workflow.add_node("rag_quality", self.nodes.check_rag_quality)
        
        # Define the flow
        workflow.set_entry_point("analyze")
        
        # Direct routing from analysis (no separate triage step needed)
        workflow.add_conditional_edges(
            "analyze",
            self._route_by_strategy,
            {
                "direct": "direct_response",
                "general_query": "general_response",
                "single_agent": "consult_agent", 
                "multi_agent": "consult_agent"
            }
        )
        
        # Direct responses go straight to quality (if enabled) or end
        if self.enable_quality_checks:
            workflow.add_edge("direct_response", "quality")
        else:
            workflow.add_edge("direct_response", END)
            
        # General responses skip quality checks and go straight to end
        workflow.add_edge("general_response", END)
        
        # Agent consultation routing - conditional based on single vs multi-agent
        workflow.add_conditional_edges(
            "consult_agent",
            self._route_after_consultation,
            {
                "single_response": "quality" if self.enable_quality_checks else END,
                "coordinate": "coordinate"
            }
        )
        
        # Quality check flow if enabled
        if self.enable_quality_checks:
            workflow.add_edge("coordinate", "quality")
            
            # After quality check, check RAG if tools were used
            workflow.add_conditional_edges(
                "quality",
                self._should_check_rag,
                {
                    "check_rag": "rag_quality",
                    "finish": END
                }
            )
            
            workflow.add_edge("rag_quality", END)
        else:
            workflow.add_edge("coordinate", END)
        
        return workflow



    def _route_by_strategy(self, state: WorkflowState) -> Literal["direct", "general_query", "single_agent", "multi_agent"]:
        """Route based on triage strategy decision."""
        strategy = state.get("response_strategy", "single_agent")
        
        if strategy == "direct":
            logger.info("Routing to direct coordinator response (cybersecurity)")
            return "direct"
        elif strategy == "general_query":
            logger.info("Routing to general assistant response")
            return "general_query"
        elif strategy == "single_agent":
            logger.info(f"Routing to single agent: {state.get('agents_to_consult', [])}")
            return "single_agent"
        else:  # multi_agent
            logger.info(f"Routing to multi-agent consultation: {state.get('agents_to_consult', [])}")
            return "multi_agent"
    
    def _route_after_consultation(self, state: WorkflowState) -> Literal["single_response", "coordinate"]:
        """
        Route after agent consultation based on whether single or multi-agent response.
        Single agent responses can skip coordinator synthesis for efficiency.
        """
        team_responses = state.get("team_responses", [])
        needs_consensus = state.get("needs_consensus", False)
        
        # If only one agent responded and consensus isn't needed, use direct response
        if len(team_responses) == 1 and not needs_consensus:
            agent_name = team_responses[0].agent_name
            confidence = team_responses[0].response.confidence_score
            logger.info(f"Single agent response from {agent_name} (confidence: {confidence:.2f}) - skipping coordinator")
            
            # Format the single response directly in state
            response = team_responses[0].response
            final_answer = f"**{team_responses[0].agent_name}'s Analysis:**\n\n"
            final_answer += f"**Summary:**\n{response.summary}\n\n"
            if response.recommendations:
                final_answer += "**Recommendations:**\n"
                for rec in response.recommendations:
                    final_answer += f"- {rec}\n"
            
            state["final_answer"] = final_answer
            state["messages"].append(AIMessage(content=final_answer))
            state["completed_at"] = datetime.now(timezone.utc)
            
            return "single_response"
        else:
            # Multiple agents or consensus needed - use coordinator
            logger.info(f"Multiple agents ({len(team_responses)}) or consensus needed - routing to coordinator")
            return "coordinate"

    def _should_consult(self, state: WorkflowState) -> Literal["consult", "coordinate"]:
        """Legacy method - kept for backward compatibility."""
        if state["agents_to_consult"]:
            logger.info(f"Proceeding to consult {len(state['agents_to_consult'])} agents in parallel.")
            return "consult"
        else:
            logger.info("No agents to consult, proceeding directly to synthesis.")
            return "coordinate"

    def _should_check_rag(self, state: WorkflowState) -> Literal["check_rag", "finish"]:
        """
        Decide if RAG quality should be checked.
        
        Args:
            state: Current workflow state
            
        Returns:
            Whether to check RAG quality or finish
        """
        # Check if any agents used tools
        has_tool_usage = any(
            len(resp.tools_used) > 0 
            for resp in state.get("team_responses", [])
        )
        
        if has_tool_usage:
            return "check_rag"
        
        return "finish"
    
    @observe(name="team_response")
    async def get_team_response(self, query: str, thread_id: str = "default") -> str:
        """
        Get a response from the cybersecurity team.
        
        Args:
            query: User query
            thread_id: Conversation thread ID
            
        Returns:
            Team's response
        """
        # Check if workflow has been compiled
        if self.app is None:
            raise RuntimeError(
                "Workflow not compiled. Use compile_with_checkpointer() or "
                "initialize through ConversationManager."
            )
        
        try:
            # Initialize state
            initial_state = {
                "query": query,
                "thread_id": thread_id,
                "response_strategy": None,
                "estimated_complexity": None,
                "messages": [],
                "team_responses": [],
                "agents_to_consult": [],
                "current_agent": None,
                "final_answer": None,
                "needs_consensus": False,
                "quality_score": None,
                "quality_passed": True,
                "rag_grounded": None,
                "rag_relevance_score": None,
                "error_count": 0,
                "last_error": None
            }
            
            # Run the workflow
            config = {"configurable": {"thread_id": thread_id}}
            result = await self.app.ainvoke(initial_state, config)
            
            return result.get("final_answer", "I apologize, but I couldn't generate a response.")
            
        except Exception as e:
            logger.error(f"Workflow error: {e}")
            return self.error_handler.get_fallback_response(str(e))
    
    def is_compiled(self) -> bool:
        """
        Check if the workflow has been compiled with a checkpointer.
        
        Returns:
            True if compiled, False otherwise
        """
        return self.app is not None
    
    async def get_state(self, thread_id: str) -> Optional[dict]:
        """
        Get the current state for a thread from the checkpointer.
        
        Args:
            thread_id: Thread identifier
            
        Returns:
            State dictionary or None
        """
        if not self.app:
            return None
        
        config = {"configurable": {"thread_id": thread_id}}
        state = await self.app.aget_state(config)
        return state.values if state else None
    
    async def update_state(self, thread_id: str, updates: dict):
        """
        Update the state for a thread in the checkpointer.
        
        Args:
            thread_id: Thread identifier
            updates: State updates to apply
        """
        if not self.app:
            raise RuntimeError("Workflow not compiled")
        
        config = {"configurable": {"thread_id": thread_id}}
        await self.app.aupdate_state(config, updates)