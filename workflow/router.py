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

from config.agent_config import AgentRole, INTERACTION_RULES, AGENT_TOOL_PERMISSIONS, TOOL_DEFINITIONS
from workflow.schemas import RoutingDecision, CybersecurityClassification

from cybersec_mcp.cybersec_tools import CybersecurityToolkit

logger = logging.getLogger(__name__)


class QueryRouter:
    """
    Routes queries to appropriate cybersecurity agents using a semantic, LLM-based approach.
    """
    
    def __init__(self, llm_client: ChatOpenAI, toolkit: CybersecurityToolkit):
        """Initialize the router with LangChain structured output capabilities and cybersecurity tools."""
        self.base_llm = llm_client
        self.toolkit = toolkit
        
        # Create structured LLMs with retry logic
        self.classification_llm = llm_client.with_structured_output(CybersecurityClassification)
        self.routing_llm = llm_client.with_structured_output(RoutingDecision)
        
        # LLM with cybersecurity tools for direct responses
        self.direct_llm = llm_client.bind_tools([
            self.toolkit.get_tool_by_name("web_search"),
            self.toolkit.get_tool_by_name("knowledge_search")
        ])
        
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
        logger.info(f"🔧 ROUTER RECEIVED: query='{query[:50]}...', context_hint={context_hint}, active_agent={active_agent}")

        # ---> REFACTORED LOGIC <---
        # PRIORITY 1: If context is maintained with a specialist, KEEP IT.
        if context_hint and context_hint != "general" and active_agent:
            logger.info(f"🔗 CONTEXT PRIORITY: Active '{context_hint}' context detected. Maintaining conversation with {active_agent.value}.")
            return RoutingDecision(
                response_strategy="single_agent",
                relevant_agents=[active_agent],
                reasoning=f"Follow-up question in an active '{context_hint}' context. Continuing with the specialist.",
                estimated_complexity="simple"
            )
        
        # PRIORITY 2: If no context, classify the new query.
        logger.info(f"🔍 No active context. Starting fresh classification for query: '{query[:50]}...'")
        is_cybersec = await self._is_cybersecurity_related(query)
        
        if not is_cybersec:
            logger.info(f"✅ General Query: Routing '{query[:50]}...' to general assistant.")
            return RoutingDecision(
                response_strategy="general_query",
                relevant_agents=[],
                reasoning="Non-cybersecurity query detected.",
                estimated_complexity="simple"
            )
        
        # PRIORITY 3: If it's a new cybersecurity query, perform full triage.
        logger.info(f"🛡️ New Cybersecurity Query: Performing full triage for '{query[:50]}...'")
        prompt = self._build_triage_prompt(query)
        
        try:
            decision = await self.routing_llm.ainvoke([
                SystemMessage(content="You are an intelligent SOC triage system. Provide structured routing decisions."),
                HumanMessage(content=prompt)
            ])
            
            logger.info(f"Triage decision for query '{query[:50]}...': {decision.response_strategy} - {decision.reasoning}")
            
            # Filter out any roles that are not actual agents
            valid_agents = [role for role in decision.relevant_agents if role in self.agent_expertise]
            decision.relevant_agents = valid_agents
            
            return decision
        
        except Exception as e:
            logger.error(f"LangChain structured triage failed: {e}")
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
        
        # Dynamically build the agent specializations and supporting tools
        agent_capabilities = []
        for role, tool_names in AGENT_TOOL_PERMISSIONS.items():
            if role == AgentRole.COORDINATOR: continue # Skip coordinator
            
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
            
        expertise_descriptions = "\n".join(agent_capabilities)
        
        return f"""
You are an intelligent SOC triage system. Your job is to determine the optimal response strategy for cybersecurity queries by routing them to the agent whose PRIMARY ROLE AND EXPERTISE best matches the user's needs.

**Core Routing Philosophy:**
🎯 **ROLE EXPERTISE FIRST** - Match the query to which agent's primary responsibility this falls under
🔧 **TOOLS SECOND** - Verify the chosen agent has necessary tools, but don't let tool quantity drive decisions
⚖️ **BALANCED ROUTING** - Avoid always choosing the agent with the most tools

**Available Response Strategies:**

1. **DIRECT** (Target: 60-70% of queries)
   - Simple factual questions ("What is NIST?", "How to report phishing?")
   - Basic definitions and explanations that don't require specialized analysis
   - → Router handles directly. Select this if no specialist expertise is needed.

2. **SINGLE_AGENT** (Target: 25-30% of queries)  
   - Query clearly falls under one agent's area of responsibility
   - Requires specialized knowledge or analysis from a domain expert
   - → Route to the agent whose primary role best matches the query intent

3. **MULTI_AGENT** (Target: 5-10% of queries)
   - Complex scenarios requiring multiple specialist perspectives
   - Incidents spanning multiple domains (e.g., breach requiring both incident response AND compliance review)
   - → Select all agents whose primary expertise is essential to address the query

**Agent Specializations & Supporting Tools:**
{expertise_descriptions}

**User Query:**
"{query}"

---
**Decision Framework:**
1. **Analyze the user's query to understand the PRIMARY INTENT and CONTEXT**
   - What is the user really trying to accomplish?
   - What type of expertise do they need?
   - Is this reactive (incident) or proactive (prevention)?

2. **Match query intent to agent PRIMARY RESPONSIBILITY**
   - Which agent's core role/expertise best aligns with this need?
   - Ignore tool counts - focus on which agent should "own" this type of request

3. **Verify the chosen agent has appropriate supporting tools**
   - Can the selected agent actually execute what's needed?
   - If not, consider if a different agent or multi-agent approach is needed

4. **Select response strategy and provide reasoning**
   - Explain why this agent's expertise matches the query
   - Mention supporting tools as validation, not primary justification

**Example Reasoning Patterns:**

✅ **Good**: "Route to INCIDENT_RESPONSE because **breach investigation and exposure checking is their primary responsibility**. They have the exposure_checker tool to execute this request."

❌ **Bad**: "Route to INCIDENT_RESPONSE because they have the most tools available (5 tools vs 3 for others)."

✅ **Good**: "Route to PREVENTION because **proactive security architecture and vulnerability management is their core expertise**. This aligns with the user's need for preventive controls."

❌ **Bad**: "Route to PREVENTION because they have vulnerability_search and threat_feeds tools."

**Complexity Guidelines:**
- **Simple**: Basic questions, definitions, general guidance
- **Moderate**: Specific analysis, single-domain problems, standard procedures  
- **Complex**: Multi-faceted incidents, cross-domain issues, strategic decisions

Focus on matching USER INTENT to AGENT EXPERTISE, not user keywords to agent tools.
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