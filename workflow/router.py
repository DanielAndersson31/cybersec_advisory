"""
Query router for determining which agents should handle a query.
Simple keyword-based routing with expertise matching.
"""

import logging
from typing import List, Dict, Any

from config.agent_config import AgentRole, EXPERTISE_DOMAINS, INTERACTION_RULES

logger = logging.getLogger(__name__)


class QueryRouter:
    """
    Routes queries to appropriate cybersecurity agents based on content.
    """
    
    def __init__(self, agents: Dict[AgentRole, Any]):
        """
        Initialize router with available agents.
        
        Args:
            agents: Dictionary of available agents
        """
        self.agents = agents
        self.expertise_domains = EXPERTISE_DOMAINS
    
    async def determine_relevant_agents(self, query: str) -> List[AgentRole]:
        """
        Determine which agents should respond to a query.
        
        Args:
            query: User query
            
        Returns:
            List of agent roles that should respond
        """
        query_lower = query.lower()
        relevant_agents = []
        
        # Check each agent's expertise against the query
        for role in AgentRole:
            if role == AgentRole.COORDINATOR:
                continue  # Coordinator doesn't directly respond
            
            if self._is_agent_relevant(role, query_lower):
                relevant_agents.append(role)
        
        # Log routing decision
        if relevant_agents:
            logger.info(f"Query matched {len(relevant_agents)} agents: {[a.value for a in relevant_agents]}")
        else:
            logger.info("No specific expertise match found")
        
        return relevant_agents
    
    def _is_agent_relevant(self, role: AgentRole, query_lower: str) -> bool:
        """
        Check if an agent's expertise matches the query.
        
        Args:
            role: Agent role to check
            query_lower: Lowercase query string
            
        Returns:
            True if agent should respond
        """
        # Check expertise domains
        domains = self.expertise_domains.get(role, [])
        for domain in domains:
            # Convert underscore to space for matching
            if domain.replace("_", " ") in query_lower:
                return True
        
        # Role-specific keyword matching
        if role == AgentRole.INCIDENT_RESPONSE:
            keywords = [
                "incident", "breach", "attack", "compromised", "infected",
                "alert", "suspicious", "malware", "ransomware", "intrusion",
                "unauthorized access", "data leak", "security event"
            ]
            if any(keyword in query_lower for keyword in keywords):
                return True
        
        elif role == AgentRole.PREVENTION:
            keywords = [
                "prevent", "secure", "harden", "protect", "vulnerability",
                "patch", "configuration", "best practice", "security control",
                "risk mitigation", "security architecture", "defense"
            ]
            if any(keyword in query_lower for keyword in keywords):
                return True
        
        elif role == AgentRole.THREAT_INTEL:
            keywords = [
                "threat", "actor", "campaign", "apt", "intelligence",
                "ioc", "indicator", "attribution", "ttps", "adversary",
                "threat landscape", "emerging threat", "zero day"
            ]
            if any(keyword in query_lower for keyword in keywords):
                return True
        
        elif role == AgentRole.COMPLIANCE:
            keywords = [
                "compliance", "gdpr", "hipaa", "pci", "sox", "iso",
                "audit", "regulation", "policy", "standard", "framework",
                "certification", "requirement", "governance"
            ]
            if any(keyword in query_lower for keyword in keywords):
                return True
        
        return False
    
    def get_primary_agent(self, agents: List[AgentRole]) -> AgentRole:
        """
        Determine the primary agent from a list of relevant agents.
        Uses the speaking order from config.
        
        Args:
            agents: List of relevant agents
            
        Returns:
            Primary agent role
        """
        if not agents:
            return AgentRole.INCIDENT_RESPONSE  # Default
        
        # Use speaking order from config
        speaking_order = INTERACTION_RULES.get("speaking_order", [])
        
        # Find first agent in speaking order
        for role in speaking_order:
            if role in agents:
                return role
        
        # Fallback to first agent
        return agents[0]