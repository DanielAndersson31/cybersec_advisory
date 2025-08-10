"""
Main workflow graph for the cybersecurity team.
Orchestrates how agents collaborate to answer queries.
"""

import logging
from typing import Literal

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langfuse.decorators import observe

from workflow.state import WorkflowState
from workflow.nodes import WorkflowNodes
from workflow.fallbacks import ErrorHandler
from agents.factory import AgentFactory

logger = logging.getLogger(__name__)


class CybersecurityTeamGraph:
    """
    Orchestrates the cybersecurity team workflow using LangGraph.
    """
    
    def __init__(self, llm, mcp_client, enable_quality_checks: bool = True):
        """
        Initialize the team workflow.
        
        Args:
            llm: Language model for agents
            mcp_client: MCP client for tools
            enable_quality_checks: Whether to enable quality gates
        """
        # Create all agents
        self.factory = AgentFactory(llm=llm, mcp_client=mcp_client)
        self.agents = self.factory.create_all_agents()
        
        # Initialize workflow components
        # Nodes now handle quality gates internally
        self.nodes = WorkflowNodes(self.agents, enable_quality_gates=enable_quality_checks)
        self.error_handler = ErrorHandler()
        self.enable_quality_checks = enable_quality_checks
        
        # Build the graph
        self.graph = self._build_graph()
        
        # Add checkpointing for conversation memory
        self.checkpointer = MemorySaver()
        self.app = self.graph.compile(checkpointer=self.checkpointer)
        
        logger.info(f"Team workflow initialized with {len(self.agents)} agents")
    
    def _build_graph(self) -> StateGraph:
        """
        Build the team collaboration graph.
        
        Returns:
            Compiled state graph
        """
        workflow = StateGraph(WorkflowState)
        
        # Add nodes
        workflow.add_node("analyze", self.nodes.analyze_query)
        workflow.add_node("route", self.nodes.route_to_agents)
        workflow.add_node("consult", self.nodes.consult_agent)
        workflow.add_node("synthesize", self.nodes.synthesize_responses)
        
        # Add quality check if enabled
        if self.enable_quality_checks:
            workflow.add_node("quality", self.nodes.check_quality)
            workflow.add_node("rag_quality", self.nodes.check_rag_quality)
        
        # Define the flow
        workflow.set_entry_point("analyze")
        workflow.add_edge("analyze", "route")
        workflow.add_edge("route", "consult")
        
        # After consulting, check if more agents needed
        workflow.add_conditional_edges(
            "consult",
            self._should_continue,
            {
                "continue": "consult",    # More agents to consult
                "synthesize": "synthesize" # All done, synthesize
            }
        )
        
        # Quality check flow if enabled
        if self.enable_quality_checks:
            workflow.add_edge("synthesize", "quality")
            
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
            workflow.add_edge("synthesize", END)
        
        return workflow
    
    def _should_continue(self, state: WorkflowState) -> Literal["continue", "synthesize"]:
        """
        Decide if more agents should be consulted.
        
        Args:
            state: Current workflow state
            
        Returns:
            Next step in workflow
        """
        # Check if we have more agents to consult
        remaining_agents = [
            agent for agent in state["agents_to_consult"]
            if not any(r.agent_role == agent for r in state["team_responses"])
        ]
        
        if remaining_agents:
            # Set next agent
            state["current_agent"] = remaining_agents[0]
            return "continue"
        
        return "synthesize"
    
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
        try:
            # Initialize state
            initial_state = {
                "query": query,
                "thread_id": thread_id,
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
            
            return result["final_answer"] or "I apologize, but I couldn't generate a response."
            
        except Exception as e:
            logger.error(f"Workflow error: {e}")
            return self.error_handler.get_fallback_response(str(e))