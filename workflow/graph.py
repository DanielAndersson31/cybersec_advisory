"""
Main workflow graph for the cybersecurity team.
Orchestrates how agents collaborate to answer queries.
"""

import logging
from typing import Literal, Optional

from langgraph.graph import StateGraph, END
from langfuse import observe

from workflow.state import WorkflowState
from workflow.nodes import WorkflowNodes
from workflow.fallbacks import ErrorHandler
from workflow.schemas import ResponseStrategy
from agents.factory import AgentFactory
from langchain_openai import ChatOpenAI
from config.settings import settings
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

        self.factory = AgentFactory(llm_client=llm_client)
        
        # Use the toolkit from the factory to avoid duplicate dependencies
        self.toolkit = self.factory.toolkit
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
        
        logger.info("Team workflow initialized.")
    
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
        workflow.add_node("check_context", self.nodes.check_context_continuity)
        workflow.add_node("general_response", self.nodes.general_response)
        workflow.add_node("direct_response", self.nodes.direct_response)
        workflow.add_node("consult_agent", self.nodes.consult_agent)
        workflow.add_node("synthesis", self.nodes.synthesize_responses)
        
        # Add quality check if enabled
        if self.enable_quality_checks:
            workflow.add_node("quality", self.nodes.check_quality)
            workflow.add_node("rag_quality", self.nodes.check_rag_quality)
        
        # Define the flow
        workflow.set_entry_point("analyze")
        
        # Direct routing from analysis to context check
        workflow.add_edge("analyze", "check_context")
        
        # After context check, route based on strategy
        workflow.add_conditional_edges(
            "check_context",
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
        
        # Agent consultation always goes to synthesis (smart synthesis handles both cases)
        workflow.add_edge("consult_agent", "synthesis")
        
        # After synthesis, go to quality check
        if self.enable_quality_checks:
            workflow.add_edge("synthesis", "quality")
        else:
            workflow.add_edge("synthesis", END)
        
        # Quality check flow if enabled
            
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
        
        return workflow

    def _route_by_strategy(self, state: WorkflowState) -> Literal["direct", "general_query", "single_agent", "multi_agent"]:
        """Route based on triage strategy decision - now using enum values."""
        strategy = state.get("response_strategy", ResponseStrategy.SINGLE_AGENT.value)
        
        # Use enum for type safety and IDE support
        if strategy == ResponseStrategy.DIRECT.value:
            return ResponseStrategy.DIRECT.value
        elif strategy == ResponseStrategy.GENERAL_QUERY.value:
            return ResponseStrategy.GENERAL_QUERY.value
        elif strategy == ResponseStrategy.SINGLE_AGENT.value:
            return ResponseStrategy.SINGLE_AGENT.value
        else:  # multi_agent
            return ResponseStrategy.MULTI_AGENT.value
    


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
    
    def _create_initial_state(
        self, 
        query: str, 
        thread_id: str, 
        conversation_history: list = None
    ) -> dict:
        """
        Create initial workflow state as a dictionary.
        WorkflowState extends MessagesState (TypedDict), not BaseModel.
        """
        return {
            "query": query,
            "thread_id": thread_id,
            "conversation_history": conversation_history or [],
            "messages": [],
            "team_responses": [],
            "agents_to_consult": [],
            "error_count": 0,
            "quality_passed": True,
            "needs_consensus": False,
        }
    
    @observe(name="team_response")
    async def get_team_response(self, query: str, thread_id: str = "default", conversation_history: list = None) -> dict:
        """
        Get a response from the cybersecurity team - now using proper state initialization.
        
        Args:
            query: User query
            thread_id: Conversation thread ID
            conversation_history: List of previous conversation messages
            
        Returns:
            Team's response
        """
        logger.info(f"--- Running New Workflow --- Query: '{query}' --- Thread: {thread_id} ---")
        # Check if workflow has been compiled
        if self.app is None:
            raise RuntimeError(
                "Workflow not compiled. Use compile_with_checkpointer() or "
                "initialize through ConversationManager."
            )
        
        try:
            # Use the new helper method for clean state initialization
            initial_state = self._create_initial_state(query, thread_id, conversation_history)
            
            # Run the workflow
            config = {"configurable": {"thread_id": thread_id}}
            result = await self.app.ainvoke(initial_state, config)
            
            return result
            
        except Exception as e:
            logger.error(f"Workflow error: {e}")
            return {
                "final_answer": self.error_handler.get_fallback_response(str(e)),
                "error_count": 1,
                "last_error": str(e)
            }
    
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