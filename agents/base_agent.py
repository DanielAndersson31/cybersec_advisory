# agents/base_agent.py

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from openai import AsyncOpenAI
from datetime import datetime
import logging

from config import (
    AgentRole,
    get_agent_config,
    get_agent_tools,
    get_quality_threshold
)

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all cybersecurity agents.
    Provides prompt construction, analysis, tool suggestion, and LangGraph compatibility.
    """

    def __init__(self, role: AgentRole, llm_client: Optional[AsyncOpenAI] = None):
        self.role = role
        self.config = get_agent_config(role)

        self.name = self.config["name"]
        self.model = self.config["model"]
        self.temperature = self.config["temperature"]
        self.max_tokens = self.config["max_tokens"]
        self.confidence_threshold = self.config["confidence_threshold"]
        self.quality_threshold = get_quality_threshold(role)
        self.allowed_tools = get_agent_tools(role)

        self.llm = llm_client or AsyncOpenAI()
        self.current_context: Dict[str, Any] = {}

        logger.info(f"Initialized agent: {self.name} ({self.role.value})")

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Role-specific system prompt"""
        pass

    async def analyze(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        use_tools: bool = True
    ) -> Dict[str, Any]:
        """Main analysis method"""
        try:
            if context:
                self.current_context.update(context)

            messages = [
                {"role": "system", "content": self.get_system_prompt()},
                {"role": "user", "content": query}
            ]

            if self.current_context:
                messages.append({
                    "role": "system",
                    "content": f"Context: {self._format_context(self.current_context)}"
                })

            response = await self.llm.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )

            agent_reply = response.choices[0].message.content
            confidence = await self.score_response(query, agent_reply)

            tool = await self.get_tool_recommendation(query) if use_tools else None

            return {
                "agent": self.name,
                "role": self.role.value,
                "response": agent_reply,
                "confidence": confidence,
                "tool_suggested": tool,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.exception(f"{self.name} analysis failed")
            return {
                "agent": self.name,
                "role": self.role.value,
                "response": f"Error: {str(e)}",
                "confidence": 0.0,
                "error": True
            }

    async def run_step(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        LangGraph-compatible interface
        Expects: { "query": str, "context": dict }
        """
        query = state.get("query", "")
        context = state.get("context", {})

        result = await self.analyze(query=query, context=context)
        return {"agent_response": result, "context": context}

    async def score_response(self, query: str, response: str) -> float:
        """
        Hook to calculate confidence (placeholder for LLM-as-a-Judge).
        Override in future to support quality gates.
        """
        return 0.75  # default fallback

    async def get_tool_recommendation(self, query: str) -> Optional[str]:
        """Keyword-based tool matching"""
        query_lower = query.lower()

        tool_keywords = {
            "ioc_analysis_tool": ["ip", "domain", "hash", "ioc"],
            "vulnerability_search_tool": ["cve", "vulnerability", "exploit"],
            "threat_feeds_tool": ["actor", "campaign", "apt"],
            "compliance_guidance_tool": ["compliance", "gdpr", "hipaa"],
            "web_search_tool": ["search", "latest", "news"],
            "knowledge_search_tool": ["playbook", "procedure", "guide"]
        }

        for tool, keywords in tool_keywords.items():
            if tool in self.allowed_tools:
                if any(keyword in query_lower for keyword in keywords):
                    return tool
        return None

    def _format_context(self, context: Dict[str, Any]) -> str:
        return "; ".join(f"{k}: {v}" for k, v in context.items())
