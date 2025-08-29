"""
Enhanced conversation history management with metadata tracking.
Keeps track of messages with a sliding window and conversation metrics.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage


class Message(BaseModel):
    """Enhanced message model with metadata tracking."""
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    agent_used: Optional[str] = None
    tools_used: List[str] = Field(default_factory=list)
    confidence_score: Optional[float] = None
    processing_time: Optional[float] = None
    message_id: str = Field(default_factory=lambda: f"msg_{datetime.now().timestamp()}")
    
    is_important: bool = False
    contains_entities: List[str] = Field(default_factory=list)


class ConversationHistory:
    """
    Enhanced conversation history with intelligent sliding window and metadata tracking.
    This is a helper for local context, LangGraph handles persistence.
    """
    
    def __init__(self, max_messages: int = 20):
        """Initialize history."""
        self.messages: List[Message] = []
        self.max_messages = max_messages
        self.conversation_start = datetime.now(timezone.utc)
        self.total_messages = 0
        self.topics_discussed: List[str] = []
    
    def add_user_message(self, content: str, entities: List[str] = None):
        """Add a user message with optional entity tracking."""
        message = Message(
            role="user", 
            content=content,
            contains_entities=entities or []
        )
        self.messages.append(message)
        self.total_messages += 1
        self._trim_history()
        return message.message_id
    
    def add_assistant_message(
        self, 
        content: str, 
        agent_used: str = None,
        tools_used: List[str] = None,
        confidence_score: float = None,
        processing_time: float = None
    ):
        """Add an assistant message with metadata."""
        message = Message(
            role="assistant", 
            content=content,
            agent_used=agent_used,
            tools_used=tools_used or [],
            confidence_score=confidence_score,
            processing_time=processing_time
        )
        self.messages.append(message)
        self.total_messages += 1
        self._trim_history()
        return message.message_id
    
    def _trim_history(self):
        """Intelligent message trimming preserving important context."""
        if len(self.messages) > self.max_messages:
            important_messages = [msg for msg in self.messages if msg.is_important]
            
            recent_count = self.max_messages - len(important_messages)
            if recent_count > 0:
                recent_messages = [
                    msg for msg in self.messages[-recent_count:] 
                    if not msg.is_important
                ]
                self.messages = important_messages + recent_messages
            else:
                self.messages = important_messages[-self.max_messages:]
    
    def get_langchain_messages(self) -> List:
        """Convert to LangChain format for workflow."""
        langchain_messages = []
        for msg in self.messages:
            if msg.role == "user":
                langchain_messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                langchain_messages.append(AIMessage(content=msg.content))
        return langchain_messages
    
    def mark_message_important(self, message_id: str):
        """Mark a message as important for context preservation."""
        for msg in self.messages:
            if msg.message_id == message_id:
                msg.is_important = True
                break
    
    def get_conversation_summary(self) -> Dict[str, Any]:
        """Get conversation statistics and summary."""
        return {
            "total_messages": self.total_messages,
            "current_length": len(self.messages),
            "conversation_duration": (datetime.now(timezone.utc) - self.conversation_start).total_seconds(),
            "agents_used": list(set(msg.agent_used for msg in self.messages if msg.agent_used)),
            "tools_used": list(set(tool for msg in self.messages for tool in msg.tools_used)),
            "topics_discussed": self.topics_discussed,
            "avg_confidence": sum(msg.confidence_score for msg in self.messages if msg.confidence_score) / max(1, len([msg for msg in self.messages if msg.confidence_score])),
        }
    
    def clear(self):
        """Clear history and reset metadata."""
        self.messages.clear()
        self.conversation_start = datetime.now(timezone.utc)
        self.total_messages = 0
        self.topics_discussed.clear()