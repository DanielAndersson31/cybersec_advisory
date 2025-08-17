"""
Workflow state definition for the cybersecurity team.
Uses Pydantic for consistency and type safety.
"""

from typing import List, Optional
from datetime import datetime
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
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    # RAG quality metrics (when using tools)
    rag_grounded: Optional[bool] = None
    rag_relevance_score: Optional[float] = None
    
    # Error handling
    error_count: int = 0
    last_error: Optional[str] = None