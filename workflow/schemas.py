from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from config.agent_config import AgentRole
from datetime import datetime, timezone

class ToolUsage(BaseModel):
    """Represents a tool that was used by an agent during analysis."""
    tool_name: str = Field(..., description="The name of the tool that was used.")
    tool_result: str = Field(..., description="The result returned by the tool.")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the tool was executed."
    )

class StructuredAgentResponse(BaseModel):
    """
    A structured response from a cybersecurity agent, designed for clarity,
    consistency, and programmatic access.
    """
    summary: str = Field(
        ...,
        description="A concise summary of the agent's analysis and findings."
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="A list of specific, actionable recommendations."
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="The agent's confidence in its analysis, from 0.0 to 1.0."
    )
    handoff_request: Optional[AgentRole] = Field(
        None,
        description="If the agent believes another specialist should take over, this field specifies which one."
    )
    tools_used: List[ToolUsage] = Field(
        default_factory=list,
        description="A list of tools that were used during the analysis."
    )

class TeamResponse(BaseModel):
    """A structured object representing a single agent's contribution to the team."""
    agent_name: str = Field(..., description="The name of the agent making the response.")
    agent_role: AgentRole = Field(..., description="The role of the agent.")
    response: StructuredAgentResponse = Field(..., description="The structured response from the agent.")
    tools_used: List[ToolUsage] = Field(
        default_factory=list,
        description="A list of tools used by the agent during its analysis.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="The timestamp of when the response was generated."
    )

class QualityGateResult(BaseModel):
    """The result of a quality gate check."""
    passed: bool = Field(description="Whether the quality gate passed.")
    feedback: str = Field(description="Detailed feedback on the quality of the response.")
    overall_score: float = Field(ge=0.0, le=10.0, description="Overall quality score from 0 to 10.")

class RAGRelevanceResult(BaseModel):
    """The result of a RAG relevance check."""
    score: float = Field(ge=0.0, le=10.0, description="Relevance score from 0 to 10.")
    is_relevant: bool = Field(description="Whether the context is relevant to the query.")
    feedback: str = Field(description="Detailed feedback on the relevance.")

class RAGGroundednessResult(BaseModel):
    """The result of a RAG groundedness check."""
    grounded: bool = Field(description="Whether the answer is grounded in the provided context.")
    feedback: str = Field(description="Detailed feedback on the groundedness.")

class CybersecurityClassification(BaseModel):
    """Classification result for cybersecurity queries."""
    is_cybersecurity_related: bool = Field(description="Whether the query is cybersecurity-related")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score between 0 and 1")
    reasoning: str = Field(max_length=200, description="Brief explanation of the classification")

class RoutingDecision(BaseModel):
    """The routing decision for a query."""
    response_strategy: str = Field(
        ...,
        description="Response strategy: 'direct', 'single_agent', 'multi_agent', 'general_query'"
    )
    relevant_agents: List[AgentRole] = Field(
        default_factory=list,
        description="A list of agent roles that are most relevant to handle the query."
    )
    reasoning: str = Field(
        ...,
        max_length=500,
        description="A brief explanation for the routing decision."
    )
    estimated_complexity: str = Field(
        ...,
        description="Complexity level: 'simple', 'moderate', 'complex'"
    )

class FinalReport(BaseModel):
    """A final, synthesized report from the Coordinator agent."""
    executive_summary: str = Field(
        ...,
        description="A high-level summary of the situation, suitable for leadership."
    )
    prioritized_recommendations: List[str] = Field(
        ...,
        description="A prioritized list of actionable recommendations, ordered from most to least critical."
    )
    conflicting_perspectives: Optional[str] = Field(
        None,
        description="If there were any significant disagreements or conflicting perspectives from the specialist agents, they are summarized here."
    )
