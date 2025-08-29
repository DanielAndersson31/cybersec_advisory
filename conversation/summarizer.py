"""
LLM-powered conversation summarizer with intelligent context preservation.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from conversation.config import ConversationConfig

logger = logging.getLogger(__name__)


class ConversationSummarizer:
    """LLM-powered conversation summarizer with intelligent context preservation."""
    
    def __init__(self, llm: Optional[ChatOpenAI] = None, config: Optional[ConversationConfig] = None):
        """Initialize with LLM for intelligent summarization and injected configuration."""
        self.config = config or ConversationConfig.from_env()
        self.llm = llm or ChatOpenAI(
            model=self.config.summarization_model,
            temperature=0.1,
            max_tokens=500
        )
    
    async def summarize_conversation(
        self, 
        messages: List[Dict[str, Any]], 
        context_type: str = "general"
    ) -> str:
        """Create intelligent LLM-based conversation summary."""
        if not messages or not self.config.enable_llm_summarization:
            return self._fallback_summary(messages)
        
        try:
            conversation_text = self._format_messages_for_summary(messages)
            system_prompt = self._get_summarization_prompt(context_type)
            
            response = await self.llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Conversation to summarize:\n\n{conversation_text}")
            ])
            
            summary = response.content.strip()
            logger.info(f"Generated LLM summary for {len(messages)} messages")
            return summary
            
        except Exception as e:
            logger.error(f"LLM summarization failed: {e}, using fallback")
            return self._fallback_summary(messages)
    
    async def identify_key_topics(self, messages: List[Dict[str, Any]]) -> List[str]:
        """Extract key topics and entities from conversation."""
        if not messages:
            return []
        
        try:
            conversation_text = self._format_messages_for_summary(messages)
            
            system_prompt = """
You are an expert at analyzing cybersecurity conversations to identify key topics and entities.

Extract the main topics, security concerns, and important entities from this conversation.
Return a JSON list of key topics/entities, focusing on:
- Security threats or incidents mentioned
- Technologies or systems discussed
- Compliance frameworks referenced  
- Key decisions or recommendations made
- Important entities (companies, people, systems)

Return only a valid JSON array of strings, nothing else.
Example: ["ransomware attack", "NIST framework", "network segmentation", "AWS infrastructure"]
"""
            
            response = await self.llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=conversation_text)
            ])
            
            import json
            try:
                topics = json.loads(response.content.strip())
                return topics if isinstance(topics, list) else []
            except json.JSONDecodeError:
                return [line.strip('- ') for line in response.content.split('\n') if line.strip()]
                
        except Exception as e:
            logger.error(f"Topic identification failed: {e}")
            return []
    
    def _format_messages_for_summary(self, messages: List[Dict[str, Any]]) -> str:
        """Format messages for LLM processing."""
        formatted = []
        for msg in messages[-20:]:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            timestamp = msg.get('timestamp', datetime.now()).strftime('%H:%M')
            
            if role == 'user':
                formatted.append(f"[{timestamp}] User: {content}")
            elif role == 'assistant':
                agent = msg.get('agent_used', 'Assistant')
                formatted.append(f"[{timestamp}] {agent}: {content}")
        
        return '\n'.join(formatted)
    
    def _get_summarization_prompt(self, context_type: str) -> str:
        """Get appropriate summarization prompt based on context."""
        base_prompt = """
You are an expert cybersecurity analyst creating conversation summaries.

Create a concise but comprehensive summary that preserves:
- Key security issues or incidents discussed
- Important recommendations or decisions made
- Technical details that provide context
- Action items or next steps mentioned
- Compliance or regulatory considerations

Focus on cybersecurity relevance and maintain technical accuracy.
Keep the summary under 300 words but ensure no critical information is lost.
"""
        
        context_prompts = {
            "incident_response": base_prompt + "\nFocus especially on incident details, timeline, and response actions.",
            "prevention": base_prompt + "\nEmphasize security controls, preventive measures, and risk mitigation strategies.",
            "compliance": base_prompt + "\nHighlight regulatory requirements, policy discussions, and compliance obligations.",
            "threat_intel": base_prompt + "\nFocus on threat analysis, indicators, and intelligence insights.",
        }
        
        return context_prompts.get(context_type, base_prompt)
    
    def _fallback_summary(self, messages: List[Dict[str, Any]]) -> str:
        """Create simple fallback summary when LLM is unavailable."""
        if not messages:
            return "No conversation history available."
        
        recent_messages = messages[-10:]
        summary_parts = []
        
        for msg in recent_messages:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')[:100]
            
            if role == 'user':
                summary_parts.append(f"User asked about: {content}...")
            elif role == 'assistant':
                agent = msg.get('agent_used', 'System')
                summary_parts.append(f"{agent} provided guidance on: {content}...")
        
        return " | ".join(summary_parts[-5:])