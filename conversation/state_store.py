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
    Wrapper for LangGraph async checkpointers that properly manages the resource lifecycle.
    """

    def __init__(self):
        self.checkpointer = None
        self._checkpointer_context = None

    async def initialize(self, persist: bool = True, db_path: str = "./conversations.db"):
        """
        Creates the checkpointer resource but does not enter the context.
        This must be called before get_checkpointer.
        """
        if persist:
            self._checkpointer_context = AsyncSqliteSaver.from_conn_string(db_path)
            logger.info(f"AsyncSqliteSaver context created for {db_path}")
        else:
            self.checkpointer = MemorySaver()
            logger.info("Using in-memory storage")

    async def get_checkpointer(self) -> Optional[AsyncSqliteSaver | MemorySaver]:
        """
        Enters the async context if needed and returns the usable checkpointer object.
        """
        if self._checkpointer_context and not self.checkpointer:
            self.checkpointer = await self._checkpointer_context.__aenter__()
            logger.info("Entered AsyncSqliteSaver context, checkpointer is active.")
        return self.checkpointer

    async def cleanup(self):
        """
        Cleans up resources by exiting the async context, which closes the connection.
        """
        if self._checkpointer_context:
            await self._checkpointer_context.__aexit__(None, None, None)
            self.checkpointer = None
            logger.info("Exited AsyncSqliteSaver context, connection is closed.")