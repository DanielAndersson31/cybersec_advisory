"""
Simple conversation history management.
Keeps track of messages with a sliding window.
"""

from typing import List, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage


class Message(BaseModel):
    """Simple message model."""
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConversationHistory:
    """
    Simple conversation history with sliding window.
    This is just a helper for local context, LangGraph handles persistence.
    """
    
    def __init__(self, max_messages: int = 20):
        """Initialize history."""
        self.messages: List[Message] = []
        self.max_messages = max_messages
    
    def add_user_message(self, content: str):
        """Add a user message."""
        self.messages.append(Message(role="user", content=content))
        self._trim_history()
    
    def add_assistant_message(self, content: str):
        """Add an assistant message."""
        self.messages.append(Message(role="assistant", content=content))
        self._trim_history()
    
    def _trim_history(self):
        """Keep only recent messages."""
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]
    
    def get_langchain_messages(self) -> List:
        """Convert to LangChain format for workflow."""
        langchain_messages = []
        for msg in self.messages:
            if msg.role == "user":
                langchain_messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                langchain_messages.append(AIMessage(content=msg.content))
        return langchain_messages
    
    def clear(self):
        """Clear history."""
        self.messages.clear()