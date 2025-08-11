"""
State store using AsyncSqliteSaver for better async performance.
"""

import logging
from typing import Optional
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver  # Async version!
from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger(__name__)


class ConversationStateStore:
    """
    Wrapper for LangGraph async checkpointers.
    """
    
    async def initialize(self, persist: bool = True, db_path: str = "./conversations.db"):
        """Initialize async checkpointer."""
        if persist:
            # Use AsyncSqliteSaver for async operations
            self.checkpointer = await AsyncSqliteSaver.from_conn_string(db_path)
            self.storage_type = "sqlite"
            logger.info(f"Using AsyncSqlite persistence: {db_path}")
        else:
            self.checkpointer = MemorySaver()
            self.storage_type = "memory"
            logger.info("Using in-memory storage")
        
        return self.checkpointer