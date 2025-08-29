"""
Enhanced schemas.py with improved organization and validation.
"""

from typing import List, Optional, Dict, Union, Literal
from pydantic import BaseModel, Field, validator, model_validator
from config.agent_config import AgentRole
from datetime import datetime, timezone
from enum import Enum


# =============================================================================
# ENUMS - Define constants as enums for better type safety
# =============================================================================

class ResponseStrategy(str, Enum):
    """Response strategy options - using enum for type safety"""
    DIRECT = "direct"
    SINGLE_AGENT = "single_agent" 
    MULTI_AGENT = "multi_agent"
    GENERAL_QUERY = "general_query"


class ComplexityLevel(str, Enum):
    """Query complexity levels"""
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


class SpecialistContext(str, Enum):
    """Types of specialist context for continuity checking"""
    INCIDENT_RESPONSE = "incident_response"
    PREVENTION = "prevention"
    THREAT_INTEL = "threat_intel"
    COMPLIANCE = "compliance"
    GENERAL = "general"


# =============================================================================
# CORE TOOL AND SEARCH MODELS
# =============================================================================

class SearchIntentResult(BaseModel):
    """Result of LLM-based search intent analysis."""
    needs_web_search: bool = Field(description="Whether the query needs current web information")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in the assessment")
    reasoning: str = Field(max_length=200, description="Brief explanation of why web search is/isn't needed")


class ToolUsage(BaseModel):
    """Represents a tool that was used by an agent during analysis."""
    tool_name: str = Field(..., min_length=1, description="The name of the tool that was used")
    tool_result: str = Field(..., description="The result returned by the tool")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the tool was executed"
    )

    @validator('tool_result')
    def validate_result_length(cls, v):
        """Ensure tool results aren't excessively long"""
        if len(v) > 10000:  # 10KB limit
            return v[:10000] + "... [truncated]"
        return v


# =============================================================================
# AGENT RESPONSE MODELS
# =============================================================================

class AgentResponse(BaseModel):
    """
    A unified response model from a cybersecurity agent.
    Supports both natural conversational responses and structured coordination responses.
    """
    # Core response fields - at least one must be provided
    content: Optional[str] = Field(
        None,
        max_length=50000,
        description="Natural, conversational response content"
    )
    summary: Optional[str] = Field(
        None,
        max_length=2000,
        description="Structured summary of analysis and findings"
    )
    
    # Optional structured fields
    recommendations: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="List of specific, actionable recommendations"
    )
    
    # Common fields for all responses
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="The agent's confidence in its analysis, from 0.0 to 1.0"
    )
    handoff_request: Optional[AgentRole] = Field(
        None,
        description="If the agent believes another specialist should take over, this field specifies which one"
    )
    tools_used: List[ToolUsage] = Field(
        default_factory=list,
        description="A list of tools that were used during the analysis"
    )

    @model_validator(mode='after')
    def validate_response_content(self):
        """Ensure at least one of content or summary is provided"""
        if not self.content and not self.summary:
            raise ValueError("Either 'content' or 'summary' must be provided")
        return self

    @validator('recommendations')
    def validate_recommendations(cls, v):
        """Ensure each recommendation is meaningful"""
        return [rec.strip() for rec in v if rec.strip()]


# =============================================================================
# TEAM COLLABORATION MODELS
# =============================================================================

class TeamResponse(BaseModel):
    """A structured object representing a single agent's contribution to the team."""
    agent_name: str = Field(..., min_length=1, description="The name of the agent making the response")
    agent_role: AgentRole = Field(..., description="The role of the agent")
    response: AgentResponse = Field(..., description="The response from the agent")
    tools_used: List[ToolUsage] = Field(
        default_factory=list,
        description="A list of tools used by the agent during its analysis"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="The timestamp of when the response was generated"
    )

    @model_validator(mode='after')
    def sync_tools_used(self):
        """Ensure tools_used is consistent between response and team_response levels"""
        if hasattr(self.response, 'tools_used') and self.response.tools_used:
            # Use tools from response if they exist
            self.tools_used = self.response.tools_used
        return self


# =============================================================================
# QUALITY AND VALIDATION MODELS
# =============================================================================

class QualityGateResult(BaseModel):
    """The result of a quality gate check."""
    passed: bool = Field(description="Whether the quality gate passed")
    feedback: str = Field(min_length=1, description="Detailed feedback on the quality of the response")
    overall_score: float = Field(ge=0.0, le=10.0, description="Overall quality score from 0 to 10")
    scores: Optional[Dict[str, float]] = Field(
        default=None, 
        description="Individual scores for each evaluation criterion (e.g., accuracy, actionability, completeness)"
    )
    
    @validator('scores')
    def validate_scores(cls, v):
        """Ensure all individual scores are within valid range."""
        if v is not None:
            for criterion, score in v.items():
                if not 0.0 <= score <= 10.0:
                    raise ValueError(f"Score for {criterion} must be between 0.0 and 10.0")
        return v

    @model_validator(mode='after')
    def validate_pass_threshold(self):
        """Ensure passed status aligns with overall score"""
        if self.overall_score < 5.0 and self.passed:
            raise ValueError("Cannot pass quality gate with score below 5.0")
        return self


class RAGRelevanceResult(BaseModel):
    """The result of a RAG relevance check."""
    score: float = Field(ge=0.0, le=10.0, description="Relevance score from 0 to 10")
    is_relevant: bool = Field(description="Whether the context is relevant to the query")
    feedback: str = Field(min_length=1, description="Detailed feedback on the relevance")

    @model_validator(mode='after')
    def sync_relevance(self):
        """Ensure relevance boolean aligns with score"""
        self.is_relevant = self.score >= 6.0
        return self


class RAGGroundednessResult(BaseModel):
    """The result of a RAG groundedness check."""
    grounded: bool = Field(description="Whether the answer is grounded in the provided context")
    feedback: str = Field(min_length=1, description="Detailed feedback on the groundedness")


# =============================================================================
# ROUTING AND CLASSIFICATION MODELS
# =============================================================================

class CybersecurityClassification(BaseModel):
    """Classification result for cybersecurity queries."""
    is_cybersecurity_related: bool = Field(description="Whether the query is cybersecurity-related")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score between 0 and 1")
    reasoning: str = Field(max_length=200, description="Brief explanation of the classification")


class ContextContinuityCheck(BaseModel):
    """Result of checking if a query maintains cybersecurity conversation context."""
    is_follow_up: bool = Field(description="Whether this is a follow-up to a previous cybersecurity conversation")
    context_maintained: bool = Field(description="Whether the cybersecurity context is maintained")
    previous_context: Optional[str] = Field(default=None, description="Summary of previous cybersecurity context")
    specialist_context: SpecialistContext = Field(description="Type of specialist context")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in the continuity assessment")
    reasoning: str = Field(max_length=300, description="Explanation of the continuity assessment")


class RoutingDecision(BaseModel):
    """The routing decision for a query."""
    response_strategy: ResponseStrategy = Field(description="Response strategy")
    relevant_agents: List[AgentRole] = Field(
        default_factory=list,
        max_length=4,  # Reasonable limit - shouldn't need all agents
        description="A list of agent roles that are most relevant to handle the query"
    )
    reasoning: str = Field(
        ...,
        max_length=500,
        min_length=1,
        description="A brief explanation for the routing decision"
    )
    estimated_complexity: ComplexityLevel = Field(description="Complexity level")

    @model_validator(mode='after')
    def validate_agent_strategy_alignment(self):
        """Ensure agent list aligns with response strategy"""
        if self.response_strategy == ResponseStrategy.GENERAL_QUERY and self.relevant_agents:
            raise ValueError("General queries should not have relevant agents")
        elif self.response_strategy == ResponseStrategy.SINGLE_AGENT and len(self.relevant_agents) != 1:
            raise ValueError("Single agent strategy must have exactly one relevant agent")
        elif self.response_strategy == ResponseStrategy.MULTI_AGENT and len(self.relevant_agents) < 2:
            raise ValueError("Multi-agent strategy must have at least two relevant agents")
        return self


# =============================================================================
# OUTPUT MODELS
# =============================================================================

class FinalReport(BaseModel):
    """A final, synthesized report from the Coordinator agent."""
    executive_summary: str = Field(
        ...,
        min_length=1,
        description="A high-level summary of the situation, suitable for leadership"
    )
    prioritized_recommendations: List[str] = Field(
        ...,
        min_length=1,
        max_length=15,
        description="A prioritized list of actionable recommendations, ordered from most to least critical"
    )
    conflicting_perspectives: Optional[str] = Field(
        None,
        description="If there were any significant disagreements or conflicting perspectives from the specialist agents, they are summarized here"
    )


class ChatResponse(BaseModel):
    """The structured response sent to the frontend for a chat message."""
    response: str = Field(..., min_length=1, description="The final, user-facing response from the agent or team")
    agent_name: Optional[str] = Field(None, description="The name of the agent who responded")
    agent_role: Optional[str] = Field(None, description="The role of the agent who responded (e.g., 'prevention')")
    tools_used: List[str] = Field(
        default_factory=list, 
        max_length=10,
        description="A list of tool names used to generate the response"
    )

    @validator('tools_used')
    def deduplicate_tools(cls, v):
        """Remove duplicate tool names"""
        return list(dict.fromkeys(v))  # Preserves order while removing duplicates