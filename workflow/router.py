"""
Query router for determining which agents should handle a query.
Uses LangChain's with_structured_output for reliable outputs with retries.
"""

import logging
from typing import List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from pydantic import ValidationError
from langfuse import observe
from dataclasses import dataclass

from config.agent_config import AgentRole, INTERACTION_RULES, AGENT_TOOL_PERMISSIONS, TOOL_DEFINITIONS
from workflow.schemas import RoutingDecision, CybersecurityClassification, ResponseStrategy

from cybersec_mcp.cybersec_tools import CybersecurityToolkit

logger = logging.getLogger(__name__)


@dataclass
class FollowUpIndicators:
    """Encapsulates logic for detecting follow-up queries"""
    strong_followup_phrases: List[str]
    new_topic_phrases: List[str]
    
    @classmethod
    def default(cls):
        return cls(
            strong_followup_phrases=[
                # Direct references to previous conversation
                "how do i", "how can i", "what's the next step", "next step",
                "how to", "walk me through", "guide me through", "show me how",
                "what should i do", "how should i", "can you help me",
                
                # Continuation words
                "also", "additionally", "furthermore", "and then", "after that",
                "what about", "what if", "but how", "but what",
                
                # Clarification requests
                "can you explain", "what does that mean", "how does that work",
                "tell me more", "elaborate", "clarify", "expand on",
                
                # Implementation questions
                "how do i implement", "how do i configure", "how do i set up",
                "where do i find", "which tool", "what command",
            ],
            new_topic_phrases=[
                # Compliance topics
                "gdpr", "hipaa", "pci-dss", "compliance", "regulation", "audit",
                "policy", "governance", "legal", "privacy law",
                
                # Prevention/architecture topics  
                "secure my network", "security architecture", "best practices",
                "vulnerability management", "patch management", "security controls",
                "firewall", "encryption", "authentication",
                
                # Threat intelligence topics
                "threat intelligence", "threat actor", "campaign analysis",
                "malware analysis", "threat hunting", "indicators of compromise",
                
                # General "what is" questions about different domains
                "what is nist", "what is iso", "what is zero trust",
                "tell me about", "explain", "what are the", "define"
            ]
        )


from workflow.system_prompts import PromptFormatter, SystemMessages, RouterPrompts


class QueryRouter:
    """Routes queries to appropriate cybersecurity agents using a semantic, LLM-based approach."""
    
    def __init__(self, llm_client: ChatOpenAI, toolkit: CybersecurityToolkit):
        """Initialize the router with LangChain structured output capabilities and cybersecurity tools."""
        self.base_llm = llm_client
        self.toolkit = toolkit
        
        self.classification_llm = llm_client.with_structured_output(CybersecurityClassification)
        self.routing_llm = llm_client.with_structured_output(RoutingDecision)
        
        self.direct_llm = llm_client.bind_tools([
            self.toolkit.get_tool_by_name("web_search"),
            self.toolkit.get_tool_by_name("knowledge_search")
        ])
        
        self.followup_indicators = FollowUpIndicators.default()
        
        # This is no longer the primary source of truth, but a fallback/supplement.
        self.agent_expertise = {
            AgentRole.INCIDENT_RESPONSE: "Handles active security incidents, breaches, malware infections, and suspicious activities. Also checks for data exposure and whether credentials have been compromised in known breaches.",
            AgentRole.PREVENTION: "Focuses on proactive defense, secure architecture, vulnerability management, and risk mitigation. Designs and recommends security controls.",
            AgentRole.THREAT_INTEL: "Analyzes threat actors, TTPs, and campaigns. Also investigates potential data exposures and tracks breach intelligence.",
            AgentRole.COMPLIANCE: "Specializes in regulatory frameworks (GDPR, HIPAA, PCI-DSS), policies, and audits. Provides guidance on governance and compliance obligations."
        }

    async def determine_routing_strategy(self, query: str, context_hint: Optional[str] = None, active_agent: Optional[AgentRole] = None) -> RoutingDecision:
        """
        Determines the optimal response strategy using intelligent triage.
        Now supports context-aware routing for persistent conversations.
        
        Args:
            query: The user's query
            context_hint: Context from previous conversation (e.g., "incident_response", "prevention")
            active_agent: Currently active agent from previous conversation
            
        Returns:
            RoutingDecision with strategy and relevant agents
        """
        # PRIORITY 1: Context-aware routing - Only for TRUE follow-ups to the same topic
        if context_hint and context_hint != "general" and active_agent:
            logger.info(f"🔗 Checking if this is a follow-up to {active_agent} ({context_hint})")
            
            if self._is_true_followup_query(query, context_hint, active_agent):
                logger.info(f"🔗 CONTEXT PRIORITY: True follow-up detected - continuing with {active_agent}")
                
                return RoutingDecision(
                    response_strategy=ResponseStrategy.SINGLE_AGENT,
                    relevant_agents=[active_agent],
                    reasoning=f"Follow-up question to {active_agent.value.replace('_', ' ')} - continuing conversation",
                    estimated_complexity="simple"
                )
            else:
                logger.info("New cybersecurity topic detected - routing based on query content")
        
        # PRIORITY 2: Cybersecurity classification (for new topics or no context)
        is_cybersec = await self._classify_cybersecurity_query(query)
        
        if not is_cybersec:
            logger.info(f"Routing '{query}' to general assistant")
            return RoutingDecision(
                response_strategy=ResponseStrategy.GENERAL_QUERY,
                relevant_agents=[],
                reasoning="Non-cybersecurity query - routing to general assistant mode",
                estimated_complexity="simple"
            )
        
        # If cybersecurity-related, use normal triage
        return await self._perform_cybersecurity_triage(query)

    async def determine_relevant_agents(self, query: str) -> List[AgentRole]:
        """
        Legacy method for backward compatibility.
        """
        decision = await self.determine_routing_strategy(query)
        return decision.relevant_agents

    def _build_agent_capabilities_description(self) -> str:
        """Build the agent capabilities section for prompts"""
        agent_capabilities = []
        for role, tool_names in AGENT_TOOL_PERMISSIONS.items():
            if role == AgentRole.COORDINATOR: 
                continue  # Skip coordinator
            
            # Start with the high-level expertise description - this is the primary focus
            expertise = self.agent_expertise.get(role, f"Specialist in {role.value.replace('_', ' ')}.")
            capability_str = f"- **{role.value}**: {expertise}"
            
            # Add supporting tools (secondary information)
            tool_descriptions = []
            for tool_name in tool_names:
                tool_def = TOOL_DEFINITIONS.get(tool_name)
                if tool_def:
                    tool_descriptions.append(f"    - `{tool_def['name']}`: {tool_def['description']}")
            
            if tool_descriptions:
                capability_str += f"\n  **Supporting Tools:**\n" + "\n".join(tool_descriptions)
            else:
                capability_str += "\n  **Supporting Tools:** No specific tools assigned."
            
            agent_capabilities.append(capability_str)
            
        return "\n".join(agent_capabilities)

    def _build_triage_prompt(self, query: str) -> str:
        """Constructs the intelligent triage prompt using centralized prompts"""
        agent_capabilities = self._build_agent_capabilities_description()
        return PromptFormatter.format_triage_prompt(query, agent_capabilities)

    def _is_true_followup_query(self, query: str, context_hint: str, active_agent: AgentRole) -> bool:
        """
        Determine if this is a true follow-up to the previous conversation.
        Now uses structured data for easier testing and maintenance.
        """
        query_lower = query.lower()
        
        # Use the structured indicators
        has_followup_phrase = any(
            phrase in query_lower 
            for phrase in self.followup_indicators.strong_followup_phrases
        )
        has_new_topic_phrase = any(
            phrase in query_lower 
            for phrase in self.followup_indicators.new_topic_phrases
        )
        
        # Apply the decision logic
        is_short_query = len(query.split()) <= 10
        
        if has_followup_phrase and not has_new_topic_phrase:
            return True  # Clear follow-up
        elif has_new_topic_phrase:
            return False  # Clear new topic
        elif is_short_query and has_followup_phrase:
            return True  # Short follow-up question
        elif len(query.split()) <= 5:
            return True  # Very short queries are usually follow-ups
        else:
            return False  # Default to new topic for longer, unclear queries

    async def _classify_cybersecurity_query(self, query: str) -> bool:
        """
        Extracted and simplified cybersecurity classification logic.
        Now more focused and easier to test.
        """
        classification_prompt = f"""
Analyze the following query and determine if it is cybersecurity-related.

Query: "{query}"

Consider these as cybersecurity-related:
- Security threats, vulnerabilities, attacks
- Data protection, privacy, encryption
- Compliance, regulations (GDPR, HIPAA, etc.)
- Incident response, forensics
- Security tools, firewalls, monitoring
- Risk assessment, security architecture
- Authentication, authorization, access control

Provide:
1. is_cybersecurity_related: boolean
2. confidence: float (0.0 to 1.0)
3. reasoning: brief explanation (max 200 chars)
"""
        
        try:

            
            # Retry logic with LangChain structured output
            for attempt in range(2):
                try:

                    classification = await self.classification_llm.ainvoke([
                        SystemMessage(content="You are a cybersecurity query classifier. Provide structured classification results."),
                        HumanMessage(content=classification_prompt)
                    ])
                    logger.info(f"Classification successful on attempt {attempt + 1}")
                    break
                except ValidationError as ve:
                    logger.error(f"Classification ValidationError on attempt {attempt + 1}: {ve}")
                    if attempt == 1:
                        raise ve
                except Exception as e:
                    logger.error(f"Classification Exception on attempt {attempt + 1}: {type(e).__name__}: {e}")
                    if attempt == 1:
                        raise e
                    logger.warning("Retrying classification...")
            
            logger.info(f"Classification result for '{query}': cybersecurity={classification.is_cybersecurity_related} "
                       f"(confidence: {classification.confidence:.2f}) - {classification.reasoning}")
            
            return classification.is_cybersecurity_related
            
        except Exception as e:
            logger.error(f"LLM classification completely failed after retries: {e}")
            logger.error(f"Query that failed classification: '{query}'")
            logger.error("This should not happen for simple queries like greetings!")
            
            # Use improved fallback logic
            return self._fallback_classification(query)

    def _fallback_classification(self, query: str) -> bool:
        """Improved fallback classification logic"""
        # Conservative fallback - default to non-cybersecurity for very short queries
        if len(query.strip()) <= 10:
            logger.warning(f"Very short query '{query}' - assuming non-cybersecurity as fallback")
            return False
        
        # Simple keyword-based fallback for longer queries
        cybersec_keywords = {
            "security", "breach", "malware", "vulnerability", "incident", "threat",
            "phishing", "ransomware", "firewall", "encryption", "compliance",
            "gdpr", "hipaa", "nist", "iso", "attack", "hack", "exploit"
        }
        query_words = set(query.lower().split())
        
        has_cybersec_keywords = bool(cybersec_keywords & query_words)
        
        if has_cybersec_keywords:
            logger.warning(f"Fallback: Found cybersecurity keywords in '{query}' - assuming cybersecurity")
            return True
        else:
            logger.warning(f"Fallback: No cybersecurity keywords in '{query}' - assuming general")
            return False

    async def _perform_cybersecurity_triage(self, query: str) -> RoutingDecision:
        """Separated cybersecurity triage logic for better organization"""
        prompt = self._build_triage_prompt(query)
        
        try:
            # Retry logic with LangChain structured output
            for attempt in range(3):
                try:
                    decision = await self.routing_llm.ainvoke([
                        SystemMessage(content=SystemMessages.SOC_TRIAGE_SYSTEM),
                        HumanMessage(content=prompt)
                    ])
                    break
                except Exception as e:
                    if attempt == 2:  # Last attempt
                        raise e
                    logger.warning(f"Routing attempt {attempt + 1} failed: {e}, retrying...")
            
            logger.info(f"Triage decision for query '{query[:50]}...': {decision.response_strategy} - {decision.reasoning}")
            
            # Filter out any roles that are not actual agents
            valid_agents = [role for role in decision.relevant_agents if role in self.agent_expertise]
            decision.relevant_agents = valid_agents
            
            return decision
        
        except Exception as e:
            logger.error(f"Cybersecurity triage failed: {e}")
            # Graceful fallback to single agent strategy
            return RoutingDecision(
                response_strategy=ResponseStrategy.SINGLE_AGENT,
                relevant_agents=[AgentRole.INCIDENT_RESPONSE],
                reasoning=f"Fallback due to routing error: {str(e)[:100]}",
                estimated_complexity="moderate"
            )

    def get_primary_agent(self, agents: List[AgentRole]) -> AgentRole:
        """
        Determines the primary agent from a list of relevant agents.
        Uses the speaking order from config.
        """
        if not agents:
            # If the LLM router returns no relevant agents, default to a generalist.
            # Incident Response is often a safe default for unknown security queries.
            logger.warning("No relevant agents identified by router. Defaulting to Incident Response.")
            return AgentRole.INCIDENT_RESPONSE
        
        speaking_order = INTERACTION_RULES.get("speaking_order", [])
        
        for role in speaking_order:
            if role in agents:
                return role
        
        return agents[0]

    @observe(name="router_direct_response")
    async def direct_response(self, query: str) -> str:
        """
        Handle direct cybersecurity queries using router's knowledge and tools.
        This is the fast path for simple cybersecurity questions.
        """
        logger.info(f"🎯 Router handling direct cybersecurity query: {query[:50]}...")
        
        system_prompt = RouterPrompts.DIRECT_RESPONSE
        
        try:
            # Use LLM with tools for direct response
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=query)
            ]
            
            # Initial response (may include tool calls)
            response = await self.direct_llm.ainvoke(messages)
            messages.append(response)
            
            # Handle tool calls if any
            if hasattr(response, 'tool_calls') and response.tool_calls:
                logger.info(f"Router making {len(response.tool_calls)} tool calls for direct response")
                
                for tool_call in response.tool_calls:
                    # Execute tool via toolkit
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]
                    tool_id = tool_call["id"]

                    try:
                        # Get the actual tool instance from toolkit
                        tool = self.toolkit.get_tool_by_name(tool_name)
                        if tool:
                            # Execute the tool with real arguments
                            real_result = await tool.ainvoke(tool_args)
                            result = str(real_result)
                        else:
                            result = f"Tool {tool_name} not found in toolkit"
                            
                        messages.append(ToolMessage(
                            content=result,
                            tool_call_id=tool_id
                        ))
                    except Exception as tool_error:
                        logger.error(f"Tool execution failed for {tool_name}: {tool_error}")
                        messages.append(ToolMessage(
                            content=f"Tool {tool_name} failed: {str(tool_error)}",
                            tool_call_id=tool_id
                        ))
                
                # Get final response after tool execution
                final_response = await self.direct_llm.ainvoke(messages)
                answer = final_response.content
            else:
                # No tools needed, use direct response
                answer = response.content
            
            logger.info("Router provided direct cybersecurity response successfully")
            return answer
            
        except Exception as e:
            logger.error(f"Router direct response failed: {e}")
            return f"I encountered an issue processing your cybersecurity query. For immediate assistance, please consult with our security specialists. Error: {str(e)[:100]}"