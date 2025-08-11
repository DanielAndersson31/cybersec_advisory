"""
Conversation manager that uses LangGraph's built-in checkpointing.
"""

import logging
from typing import Dict, Any, Optional

from langfuse.decorators import observe

from conversation.history import ConversationHistory
from conversation.state_store import ConversationStateStore

logger = logging.getLogger(__name__)


class ConversationManager:
    """
    Manager that coordinates conversation using LangGraph checkpointing.
    """
    
    def __init__(self, workflow, use_persistent_storage: bool = True):
        """
        Initialize with workflow that already has LangGraph checkpointing.
        
        Args:
            workflow: CybersecurityTeamGraph with checkpointer
            use_persistent_storage: Use SQLite (True) or memory (False)
        """
        self.workflow = workflow
        
        # If workflow doesn't have a checkpointer, add one
        if not hasattr(workflow, 'checkpointer') or workflow.checkpointer is None:
            store = ConversationStateStore(persist=use_persistent_storage)
            workflow.checkpointer = store.get_checkpointer()
            workflow.app = workflow.graph.compile(checkpointer=workflow.checkpointer)
            logger.info("Added checkpointer to workflow")
        
        # Local cache for quick access
        self.history_cache: Dict[str, ConversationHistory] = {}
    
    @observe(name="chat")
    async def chat(self, message: str, thread_id: str = "default") -> str:
        """
        Chat interface - LangGraph handles all persistence via thread_id.
        
        Args:
            message: User message
            thread_id: Conversation thread ID (used by LangGraph for persistence)
            
        Returns:
            Assistant response
        """
        # Local history for context
        if thread_id not in self.history_cache:
            self.history_cache[thread_id] = ConversationHistory()
        
        history = self.history_cache[thread_id]
        history.add_user_message(message)
        
        try:
            # LangGraph automatically loads/saves state based on thread_id
            response = await self.workflow.get_team_response(
                query=message,
                thread_id=thread_id
            )
            
            history.add_assistant_message(response)
            return response
            
        except Exception as e:
            logger.error(f"Error in chat: {e}")
            return "I apologize, but I encountered an error processing your request."
    
    async def get_state(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Get conversation state from LangGraph."""
        config = {"configurable": {"thread_id": thread_id}}
        state = await self.workflow.app.aget_state(config)
        return state.values if state else None
    
    async def clear(self, thread_id: str):
        """Clear conversation."""
        if thread_id in self.history_cache:
            del self.history_cache[thread_id]
        
        # Reset in LangGraph
        config = {"configurable": {"thread_id": thread_id}}
        await self.workflow.app.aupdate_state(config, {"messages": []})