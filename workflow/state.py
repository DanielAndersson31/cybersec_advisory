from typing import List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from langgraph.graph import MessagesState
from config.agent_config import AgentRole
from .schemas import TeamResponse, SearchIntentResult


class ConversationTurn(BaseModel):
    """A single turn in the conversation history."""
    role: str = Field(..., description="The role of the speaker (user, assistant, system)")
    content: str = Field(..., description="The content of the message")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the message was created"
    )
    agent_used: Optional[AgentRole] = Field(
        None, 
        description="Agent that generated this turn (if applicable)"
    )


class WorkflowState(MessagesState):
    """
    State that flows through the cybersecurity team workflow.
    Extends MessagesState to maintain conversation history.
    """
    # User query
    query: str = Field(..., description="The user's original query")
   
    # Triage and routing
    response_strategy: Optional[str] = Field(
        None, 
        description="Response strategy: 'direct', 'single_agent', 'multi_agent', 'general_query'"
    )
    estimated_complexity: Optional[str] = Field(
        None,
        description="Complexity level: 'simple', 'moderate', 'complex'"
    )
   
    # Agent persistence - Track active agent for follow-ups
    active_agent: Optional[AgentRole] = Field(
        None,
        description="Agent currently leading the conversation"
    )
    conversation_context: Optional[str] = Field(
        None,
        description="Conversation domain context: 'cybersecurity', 'general', etc."
    )
   
    # Web search intent detection (now properly typed)
    web_search_intent: Optional[SearchIntentResult] = Field(
        None,
        description="Result of LLM-based search intent analysis"
    )
   
    # Team collaboration
    team_responses: List[TeamResponse] = Field(
        default_factory=list,
        description="Responses from team agents during collaboration"
    )
    agents_to_consult: List[AgentRole] = Field(
        default_factory=list,
        description="List of agents that should be consulted for this query"
    )
   
    # Final output
    final_answer: Optional[str] = Field(
        None,
        description="The final synthesized response to the user"
    )
    needs_consensus: bool = Field(
        default=False,
        description="Whether multiple agents need to reach consensus"
    )
   
    # Quality control
    quality_score: Optional[float] = Field(
        None,
        ge=0.0,
        le=10.0,
        description="Overall quality score from 0 to 10"
    )
    quality_passed: bool = Field(
        default=True,
        description="Whether the response passed quality checks"
    )
   
    # Workflow metadata
    thread_id: str = Field(
        default="default",
        description="Unique identifier for this conversation thread"
    )
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the workflow was initiated"
    )
    completed_at: Optional[datetime] = Field(
        None,
        description="When the workflow was completed"
    )
   
    # RAG quality metrics (when using tools)
    rag_grounded: Optional[bool] = Field(
        None,
        description="Whether the response is grounded in retrieved context"
    )
    rag_relevance_score: Optional[float] = Field(
        None,
        ge=0.0,
        le=10.0,
        description="Relevance score of retrieved context (0-10)"
    )
   
    # Error handling
    error_count: int = Field(
        default=0,
        ge=0,
        description="Number of errors encountered during workflow"
    )
    last_error: Optional[str] = Field(
        None,
        description="Description of the most recent error"
    )
   
    # Conversation context
    conversation_history: List[ConversationTurn] = Field(
        default_factory=list,
        description="Structured history of the conversation turns"
    )