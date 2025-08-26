"""
Simplified Cybersecurity Toolkit
Direct tool implementations without HTTP overhead - Production-ready approach.
"""

import logging
from typing import List, Optional

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from openai import AsyncOpenAI
from config.settings import settings

from cybersec_mcp.tools import (
    AttackSurfaceAnalyzerTool,
    ComplianceGuidanceTool,
    ExposureCheckerTool,
    IOCAnalysisTool,
    KnowledgeSearchTool,
    ThreatFeedsTool,
    VulnerabilitySearchTool,
    WebSearchTool,
)

logger = logging.getLogger(__name__)


class CybersecurityToolkit(BaseModel):
    """A toolkit for cybersecurity operations."""
    tools: List[BaseTool] = Field(default_factory=list)

    def __init__(self, **data):
        super().__init__(**data)
        llm_client = AsyncOpenAI(api_key=settings.get_secret("openai_api_key"))
        self.tools = [
            AttackSurfaceAnalyzerTool(),
            ComplianceGuidanceTool(),
            ExposureCheckerTool(),
            IOCAnalysisTool(),
            KnowledgeSearchTool(),
            ThreatFeedsTool(),
            VulnerabilitySearchTool(),
            WebSearchTool(llm_client=llm_client),
        ]
        logger.info("Cybersecurity toolkit created with %d tools.", len(self.tools))

    def get_all_tools(self) -> List[BaseTool]:
        """Returns all tools in the toolkit."""
        return self.tools

    def get_tool_by_name(self, name: str) -> Optional[BaseTool]:
        """Returns a tool by its name."""
        for tool in self.tools:
            if tool.name == name:
                return tool
        return None
