"""
State store is just a thin wrapper since LangGraph handles persistence.
"""

import logging
from typing import Optional, Dict, Any
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger(__name__)


class ConversationStateStore:
    """
    Simple wrapper for LangGraph checkpointers.
    LangGraph handles all the actual persistence.
    """
    
    def __init__(self, persist: bool = True, db_path: str = "./conversations.db"):
        """Initialize with LangGraph checkpointer."""
        if persist:
            self.checkpointer = SqliteSaver.from_conn_string(db_path)
            self.storage_type = "sqlite"
            logger.info(f"Using SQLite persistence: {db_path}")
        else:
            self.checkpointer = MemorySaver()
            self.storage_type = "memory"
            logger.info("Using in-memory storage")
    
    def get_checkpointer(self):
        """Get the checkpointer for workflow compilation."""
        return self.checkpointer