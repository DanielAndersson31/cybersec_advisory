"""
Conversation manager with async checkpointer initialization.
"""

import logging
from typing import Dict, Any, Optional

from langfuse import observe

from conversation.history import ConversationHistory
from conversation.state_store import ConversationStateStore

logger = logging.getLogger(__name__)


class ConversationManager:
    """
    Manager that coordinates conversation using LangGraph checkpointing.
    """
    
    def __init__(self, workflow):
        """Initialize with workflow."""
        self.workflow = workflow
        self.history_cache: Dict[str, ConversationHistory] = {}
        self.initialized = False
    
    async def initialize(self, use_persistent_storage: bool = True, db_path: str = "./conversations.db"):
        """
        Async initialization to set up checkpointer.
        Must be called before using the manager.
        """
        # Create state store with async checkpointer
        store = ConversationStateStore()
        checkpointer = await store.initialize(persist=use_persistent_storage, db_path=db_path)
        
        # Compile workflow with checkpointer
        self.workflow.compile_with_checkpointer(checkpointer)
        
        self.initialized = True
        logger.info("Conversation manager initialized with async checkpointer")
    
    @observe(name="chat")
    async def chat(self, message: str, thread_id: str = "default") -> str:
        """Chat interface."""
        if not self.initialized:
            raise RuntimeError("ConversationManager not initialized. Call await manager.initialize() first.")
        
        # Rest stays the same...
        if thread_id not in self.history_cache:
            self.history_cache[thread_id] = ConversationHistory()
        
        history = self.history_cache[thread_id]
        history.add_user_message(message)
        
        try:
            response = await self.workflow.get_team_response(
                query=message,
                thread_id=thread_id
            )
            
            history.add_assistant_message(response)
            return response
            
        except Exception as e:
            logger.error(f"Error in chat: {e}")
            return "I apologize, but I encountered an error processing your request."