from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import Field
from langgraph.graph import MessagesState

from config.agent_config import AgentRole
from .schemas import TeamResponse


class WorkflowState(MessagesState):
    """
    State that flows through the cybersecurity team workflow.
    Extends MessagesState to maintain conversation history.
    """
    # User query
    query: str
    
    # Triage and routing
    response_strategy: Optional[str] = None  # "direct", "single_agent", "multi_agent"
    estimated_complexity: Optional[str] = None  # "simple", "moderate", "complex"
    
    # Agent persistence - NEW: Track active agent for follow-ups
    active_agent: Optional[AgentRole] = None  # Track who's "leading" the conversation
    conversation_context: Optional[str] = None  # Track conversation domain (cybersecurity, general)
    
    # Web search intent detection (contextual for agents)
    web_search_intent: Optional[Dict[str, Any]] = None
    
    # Team collaboration
    team_responses: List[TeamResponse] = Field(default_factory=list)
    agents_to_consult: List[AgentRole] = Field(default_factory=list)
    current_agent: Optional[AgentRole] = None
    
    # Final output
    final_answer: Optional[str] = None
    needs_consensus: bool = False
    
    # Quality control (optional)
    quality_score: Optional[float] = None
    quality_passed: bool = True
    
    # Workflow metadata
    thread_id: str = Field(default="default")
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    
    # RAG quality metrics (when using tools)
    rag_grounded: Optional[bool] = None
    rag_relevance_score: Optional[float] = None
    
    # Error handling
    error_count: int = 0
    last_error: Optional[str] = None
    
    # Conversation context
    conversation_history: List[Dict[str, Any]] = Field(default_factory=list)