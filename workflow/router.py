"""
Query router for determining which agents should handle a query.
Uses LangChain's with_structured_output for reliable outputs with retries.
"""

import logging
from typing import List
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from pydantic import ValidationError
from langfuse import observe

from config.agent_config import AgentRole, INTERACTION_RULES
from workflow.schemas import RoutingDecision, CybersecurityClassification
# No longer need MCP client - using direct tools!

logger = logging.getLogger(__name__)


class QueryRouter:
    """
    Routes queries to appropriate cybersecurity agents using a semantic, LLM-based approach.
    """
    
    def __init__(self, llm_client: ChatOpenAI):
        """Initialize the router with LangChain structured output capabilities and cybersecurity tools."""
        self.base_llm = llm_client
        
        # Create structured LLMs with retry logic
        self.classification_llm = llm_client.with_structured_output(CybersecurityClassification)
        self.routing_llm = llm_client.with_structured_output(RoutingDecision)
        
        # LLM with cybersecurity tools for direct responses
        from cybersec_tools import cybersec_toolkit
        self.direct_llm = llm_client.bind_tools([
            cybersec_toolkit.search_web,
            cybersec_toolkit.search_knowledge_base
        ])
        
        self.agent_expertise = {
            AgentRole.INCIDENT_RESPONSE: "Handles active security incidents, breaches, malware infections, and suspicious activities. Focuses on containment, eradication, and recovery.",
            AgentRole.PREVENTION: "Focuses on proactive defense, secure architecture, vulnerability management, and risk mitigation. Designs and recommends security controls.",
            AgentRole.THREAT_INTEL: "Analyzes threat actors, their tactics (TTPs), and campaigns. Provides deep, contextualized intelligence on adversary motives and likely future actions.",
            AgentRole.COMPLIANCE: "Specializes in regulatory frameworks (GDPR, HIPAA, PCI-DSS), policies, and audits. Provides guidance on governance and compliance obligations."
        }

    async def determine_routing_strategy(self, query: str) -> RoutingDecision:
        """
        Determines the optimal response strategy using intelligent triage.
        First checks if query is cybersecurity-related, then routes appropriately.
        """
        # Quick pre-check: Is this cybersecurity-related?
        logger.info(f"🔍 Starting cybersecurity classification for query: '{query}'")
        is_cybersec = await self._is_cybersecurity_related(query)
        logger.info(f"📋 Classification result: cybersecurity_related={is_cybersec}")
        
        if not is_cybersec:
            logger.info(f"✅ Routing '{query}' to general assistant (non-cybersecurity)")
            return RoutingDecision(
                response_strategy="general_query",
                relevant_agents=[],
                reasoning="Non-cybersecurity query - routing to general assistant mode",
                estimated_complexity="simple"
            )
        
        # If cybersecurity-related, use normal triage
        prompt = self._build_triage_prompt(query)
        
        try:
            # Retry logic with LangChain structured output
            for attempt in range(3):
                try:
                    decision = await self.routing_llm.ainvoke([
                        SystemMessage(content="You are an intelligent SOC triage system. Provide structured routing decisions."),
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
            logger.error(f"LangChain structured triage failed after retries: {e}")
            # Graceful fallback to single agent strategy
            return RoutingDecision(
                response_strategy="single_agent",
                relevant_agents=[AgentRole.INCIDENT_RESPONSE],
                reasoning=f"Fallback due to routing error: {str(e)[:100]}",
                estimated_complexity="moderate"
            )

    async def determine_relevant_agents(self, query: str) -> List[AgentRole]:
        """
        Legacy method for backward compatibility.
        """
        decision = await self.determine_routing_strategy(query)
        return decision.relevant_agents

    def _build_triage_prompt(self, query: str) -> str:
        """Constructs the intelligent triage prompt for response strategy determination."""
        expertise_descriptions = "\\n".join(
            f"- **{role.value}**: {desc}" for role, desc in self.agent_expertise.items()
        )
        
        return f"""
You are an intelligent SOC triage system. Your job is to determine the optimal response strategy for cybersecurity queries, mirroring how real Security Operations Centers work.

**Available Response Strategies:**

1. **DIRECT** (Target: 60-70% of queries)
   - Simple factual questions ("What is NIST?", "How to report phishing?")
   - Basic definitions and explanations
   - General cybersecurity guidance
   - Knowledge base lookups
   → Router handles directly with cybersecurity tools

2. **SINGLE_AGENT** (Target: 25-30% of queries)  
   - Requires specific domain expertise
   - Investigation or analysis needed
   - One specialist perspective sufficient
   → Route to one appropriate specialist

3. **MULTI_AGENT** (Target: 5-10% of queries)
   - Major incidents requiring multiple perspectives
   - Complex scenarios spanning multiple domains
   - High-stakes decisions needing consensus
   → Full team consultation needed

**Specialist Agent Expertise:**
{expertise_descriptions}

**User Query:**
"{query}"

---
**Instructions:**
1. **Analyze the query complexity and type**
2. **Determine the optimal response strategy** based on SOC triage principles
3. **If single/multi-agent**, select the most relevant specialist(s)
4. **Provide clear reasoning** for your triage decision
5. **Estimate complexity level**: simple, moderate, complex

**Remember**: Bias toward faster responses. Only escalate to specialists when their expertise is truly needed.
"""

    async def _is_cybersecurity_related(self, query: str) -> bool:
        """
        Quick classification to determine if query is cybersecurity-related.
        Fast check before full triage.
        """
        classification_prompt = f"""
Classify this query as cybersecurity-related or not and provide your reasoning.

CYBERSECURITY-RELATED includes:
- Security incidents, threats, vulnerabilities
- Malware, phishing, attacks, breaches  
- Compliance, policies, risk management
- Security tools, frameworks (NIST, ISO 27001, etc.)
- Network security, access control, encryption
- Security monitoring, SOC operations
- Incident response, forensics

NOT CYBERSECURITY-RELATED includes:
- General questions (time, weather, directions)
- Basic definitions unrelated to security
- Personal assistance requests
- General technology questions
- Business questions unrelated to security

Query: "{query}"

Provide a classification with confidence score and reasoning.
"""
        
        try:
            logger.info(f"🚀 Starting LLM classification for query: '{query}'")
            
            # Retry logic with LangChain structured output
            for attempt in range(2):
                try:
                    logger.info(f"🔄 Classification attempt {attempt + 1} for query: '{query}'")
                    classification = await self.classification_llm.ainvoke([
                        SystemMessage(content="You are a cybersecurity query classifier. Provide structured classification results."),
                        HumanMessage(content=classification_prompt)
                    ])
                    logger.info(f"✅ Classification successful on attempt {attempt + 1}")
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
            
            logger.info(f"✅ Classification result for '{query}': cybersecurity={classification.is_cybersecurity_related} "
                       f"(confidence: {classification.confidence:.2f}) - {classification.reasoning}")
            
            return classification.is_cybersecurity_related
            
        except Exception as e:
            logger.error(f"LangChain classification completely failed after retries: {e}")
            logger.error(f"Query that failed classification: '{query}'")
            logger.error("This should not happen for simple queries like greetings!")
            
            # Conservative fallback - default to non-cybersecurity for very short queries
            if len(query.strip()) <= 10:
                logger.warning(f"Very short query '{query}' - assuming non-cybersecurity as fallback")
                return False
            else:
                logger.warning(f"Complex query '{query}' - defaulting to cybersecurity as fallback")
                return True

    def _build_routing_prompt(self, query: str) -> str:
        """Legacy method - use _build_triage_prompt instead."""
        return self._build_triage_prompt(query)

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
        
        system_prompt = """
You are a cybersecurity SOC analyst providing direct responses to common cybersecurity queries. 
You have access to tools for searching web resources and knowledge bases when needed.

**Your Role:**
- Answer simple cybersecurity questions directly using your knowledge
- Use search_knowledge_base for organizational policies and procedures
- Use web_search_tool for current threat intelligence and best practices  
- Provide clear, accurate, actionable guidance
- Be concise but comprehensive

**Available Tools:**
🌐 **web_search_tool** - Search current cybersecurity information
📚 **search_knowledge_base** - Search internal knowledge base

**Response Guidelines:**
- For basic definitions: Answer directly with your knowledge
- For current threats/news: Use web search
- For policies/procedures: Use knowledge base search  
- Always include practical next steps when relevant
- Be professional but accessible

**Example Usage:**
- "What is NIST?" → Direct answer with framework overview
- "Latest ransomware threats" → Web search for current intel
- "Incident response process" → Knowledge base search

Focus on being helpful and accurate. If the question requires specialized analysis, indicate that specialist consultation would be beneficial.
"""
        
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
                    try:
                        # Execute tool via MCP client
                        tool_name = tool_call["name"]
                        tool_args = tool_call["args"]
                        
                        # Tools are now executed directly by LangChain - much simpler!
                        result = f"Tool {tool_name} executed successfully"
                        
                        # Add tool result to messages
                        messages.append(ToolMessage(
                            content=str(result), 
                            tool_call_id=tool_call["id"]
                        ))
                        
                    except Exception as tool_error:
                        logger.error(f"Tool execution failed for {tool_name}: {tool_error}")
                        messages.append(ToolMessage(
                            content=f"Tool {tool_name} failed: {str(tool_error)}", 
                            tool_call_id=tool_call["id"]
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