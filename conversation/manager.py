"""
Enhanced conversation manager with retry logic and metadata tracking.
"""

import logging
import time
from typing import Dict, Any, Optional, List

from langfuse import observe
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from conversation.history import ConversationHistory, Message
from conversation.state_store import ConversationStateStore
from conversation.config import conversation_config
from conversation.summarizer import ConversationSummarizer

logger = logging.getLogger(__name__)


class ConversationManager:
    """
    Enhanced manager that coordinates conversation using LangGraph checkpointing with retry logic and metadata tracking.
    """
    
    def __init__(self, workflow, llm_client=None):
        """Initialize with workflow and optional LLM client."""
        self.workflow = workflow
        self.store = ConversationStateStore()
        self.history_cache: Dict[str, ConversationHistory] = {}
        self.config = conversation_config
        self.initialized = False
        
        # Initialize summarizer with LLM support
        self.summarizer = ConversationSummarizer(llm_client) if llm_client else ConversationSummarizer()
        
        # Metrics tracking
        self.metrics = {
            "total_conversations": 0,
            "total_messages": 0,
            "avg_response_time": 0.0,
            "error_count": 0,
        }
    
    async def initialize(self, use_persistent_storage: bool = False, db_path: str = None):
        """
        Async initialization to set up checkpointer with configuration.
        Must be called before using the manager.
        """
        # Force in-memory storage for simplicity
        use_persistent_storage = False
        
        # Initialize the store and get the checkpointer
        await self.store.initialize(persist=use_persistent_storage, db_path=db_path)
        checkpointer = await self.store.get_checkpointer()
        
        if checkpointer:
            # Compile workflow with checkpointer
            self.workflow.compile_with_checkpointer(checkpointer)
            self.initialized = True
            logger.info(f"Conversation manager initialized with in-memory storage (localStorage for frontend)")
        else:
            logger.error("Failed to get checkpointer from state store.")
            self.initialized = False

    async def cleanup(self):
        """Clean up resources held by the manager."""
        await self.store.cleanup()
        logger.info("Conversation manager cleaned up.")

    @observe(name="chat")
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1.5, max=60),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        reraise=True
    )
    async def chat(self, message: str, thread_id: str = "default") -> str:
        """Enhanced chat interface with retry logic and metadata tracking."""
        if not self.initialized:
            raise RuntimeError("ConversationManager not initialized. Call await manager.initialize() first.")
        
        start_time = time.time()
        
        # Initialize conversation if new
        if thread_id not in self.history_cache:
            self.history_cache[thread_id] = ConversationHistory(
                max_messages=self.config.max_messages_per_thread
            )
            self.metrics["total_conversations"] += 1
        
        history = self.history_cache[thread_id]
        
        # Add user message with entity extraction
        entities = await self._extract_entities(message) if self.config.enable_smart_context_preservation else []
        history.add_user_message(message, entities=entities)
        
        try:
            # Convert conversation history to the format expected by the workflow
            conversation_history = []
            for msg in history.messages:
                conversation_history.append({
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat(),
                    "agent_used": msg.agent_used
                })
            
            # Get workflow response
            response = await self.workflow.get_team_response(
                query=message,
                thread_id=thread_id,
                conversation_history=conversation_history
            )
            
            # Calculate processing time
            processing_time = time.time() - start_time
            
            # Extract metadata from response if available
            agent_used = self._extract_agent_from_response(response)
            tools_used = self._extract_tools_from_response(response)
            confidence_score = self._extract_confidence_from_response(response)
            
            # Add assistant message with metadata
            history.add_assistant_message(
                response,
                agent_used=agent_used,
                tools_used=tools_used,
                confidence_score=confidence_score,
                processing_time=processing_time
            )
            
            # Update metrics
            self.metrics["total_messages"] += 2  # User + assistant
            self._update_avg_response_time(processing_time)
            
            # Check if conversation needs summarization
            if len(history.messages) > self.config.auto_summarize_threshold:
                await self._auto_summarize_if_needed(thread_id, history)
            
            return response
            
        except Exception as e:
            self.metrics["error_count"] += 1
            logger.error(f"Error in chat for thread {thread_id}: {e}")
            
            # Add error context to history
            error_msg = "I apologize, but I encountered an error processing your request. Please try again."
            history.add_assistant_message(error_msg, processing_time=time.time() - start_time)
            
            return error_msg
    
    async def get_conversation_summary(self, thread_id: str) -> Optional[str]:
        """Get intelligent summary of conversation."""
        if thread_id not in self.history_cache:
            return None
        
        history = self.history_cache[thread_id]
        messages = [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp,
                "agent_used": msg.agent_used
            }
            for msg in history.messages
        ]
        
        # Determine context type based on agents used
        agents_used = set(msg.agent_used for msg in history.messages if msg.agent_used)
        context_type = self._determine_context_type(agents_used)
        
        return await self.summarizer.summarize_conversation(messages, context_type)
    
    async def _extract_entities(self, message: str) -> List[str]:
        """Extract key entities from user message."""
        try:
            # Simple keyword-based entity extraction for now
            # Could be enhanced with NER models
            security_keywords = [
                "malware", "ransomware", "phishing", "ddos", "breach", "vulnerability",
                "firewall", "endpoint", "network", "authentication", "encryption"
            ]
            
            entities = [keyword for keyword in security_keywords if keyword.lower() in message.lower()]
            return entities
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return []
    
    def _extract_agent_from_response(self, response: str) -> Optional[str]:
        """Extract which agent provided the response."""
        # Look for agent names in response
        agent_indicators = {
            "Sarah Chen": ["incident", "response", "breach", "attack"],
            "Alex Rodriguez": ["prevention", "security controls", "architecture"],
            "Dr. Kim Park": ["threat", "intelligence", "analysis", "actor"],
            "Maria Santos": ["compliance", "regulation", "policy", "audit"]
        }
        
        response_lower = response.lower()
        for agent, keywords in agent_indicators.items():
            if any(keyword in response_lower for keyword in keywords):
                return agent
        
        return "Cybersecurity Team"
    
    def _extract_tools_from_response(self, response: str) -> List[str]:
        """Extract which tools were used based on response content."""
        tools = []
        response_lower = response.lower()
        
        if "searching" in response_lower or "found information" in response_lower:
            tools.append("web_search")
        if "knowledge base" in response_lower:
            tools.append("knowledge_search")
        if "analysis" in response_lower and "threat" in response_lower:
            tools.append("threat_analysis")
        
        return tools
    
    def _extract_confidence_from_response(self, response: str) -> Optional[float]:
        """Extract confidence score from response."""
        # Simple heuristic based on response characteristics
        if len(response) > 500 and "recommend" in response.lower():
            return 0.9
        elif len(response) > 200:
            return 0.7
        else:
            return 0.5
    
    def _update_avg_response_time(self, processing_time: float):
        """Update average response time metric."""
        current_avg = self.metrics["avg_response_time"]
        total_messages = self.metrics["total_messages"]
        
        if total_messages > 0:
            self.metrics["avg_response_time"] = (
                (current_avg * (total_messages - 1) + processing_time) / total_messages
            )
        else:
            self.metrics["avg_response_time"] = processing_time
    
    def _determine_context_type(self, agents_used: set) -> str:
        """Determine conversation context type based on agents involved."""
        if "Sarah Chen" in agents_used:
            return "incident_response"
        elif "Alex Rodriguez" in agents_used:
            return "prevention"
        elif "Dr. Kim Park" in agents_used:
            return "threat_intel"
        elif "Maria Santos" in agents_used:
            return "compliance"
        else:
            return "general"
    
    async def _auto_summarize_if_needed(self, thread_id: str, history: ConversationHistory):
        """Auto-summarize conversation if it gets too long."""
        if not self.config.enable_llm_summarization:
            return
        
        try:
            # Create summary of older messages
            messages_to_summarize = history.messages[:-self.config.max_messages_per_thread//2]
            if len(messages_to_summarize) > 5:  # Only summarize if worth it
                
                messages_dict = [
                    {
                        "role": msg.role,
                        "content": msg.content,
                        "timestamp": msg.timestamp,
                        "agent_used": msg.agent_used
                    }
                    for msg in messages_to_summarize
                ]
                
                agents_used = set(msg.agent_used for msg in messages_to_summarize if msg.agent_used)
                context_type = self._determine_context_type(agents_used)
                
                summary = await self.summarizer.summarize_conversation(messages_dict, context_type)
                
                # Replace old messages with summary
                summary_message = Message(
                    role="system",
                    content=f"[Conversation Summary]: {summary}",
                    is_important=True
                )
                
                # Keep recent messages and add summary
                recent_messages = history.messages[-self.config.max_messages_per_thread//2:]
                history.messages = [summary_message] + recent_messages
                
                logger.info(f"Auto-summarized conversation {thread_id} - compressed {len(messages_to_summarize)} messages")
                
        except Exception as e:
            logger.error(f"Auto-summarization failed for {thread_id}: {e}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get conversation manager metrics."""
        return {
            **self.metrics,
            "active_threads": len(self.history_cache),
            "avg_conversation_length": sum(len(h.messages) for h in self.history_cache.values()) / max(1, len(self.history_cache))
        }