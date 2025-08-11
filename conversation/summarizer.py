"""
Simple summarizer for long conversations.
"""

import logging
from typing import List

logger = logging.getLogger(__name__)


class ConversationSummarizer:
    """Simple conversation summarizer."""
    
    def __init__(self, llm=None):
        """Initialize with optional LLM."""
        self.llm = llm
    
    def summarize(self, messages: List[str], max_length: int = 500) -> str:
        """Create simple summary."""
        if not messages:
            return ""
        
        # Simple extractive summary
        summary_parts = []
        for i, msg in enumerate(messages[:5]):  # First 5 messages
            if i % 2 == 0:  # User messages
                summary_parts.append(f"Asked: {msg[:50]}...")
            else:  # Assistant messages
                summary_parts.append(f"Explained: {msg[:50]}...")
        
        summary = " ".join(summary_parts)
        return summary[:max_length] if len(summary) > max_length else summary