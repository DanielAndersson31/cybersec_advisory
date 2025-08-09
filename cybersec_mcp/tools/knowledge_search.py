"""
Knowledge search tool for internal cybersecurity documentation and playbooks.
"""

from typing import Dict, Any, List, Optional
import logging
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class KnowledgeResultMetadata(BaseModel):
    """Metadata for a knowledge base document."""
    doc_id: str
    last_updated: str
    tags: List[str]
    author: str

class KnowledgeResult(BaseModel):
    """A single result from a knowledge base search."""
    title: str
    category: str
    summary: str
    relevance_score: float
    metadata: Optional[KnowledgeResultMetadata] = None

class KnowledgeSearchResponse(BaseModel):
    """The structured response for a knowledge search query."""
    status: str = "success"
    query: str
    categories_searched: List[str]
    results: List[KnowledgeResult]
    total_results: int
    error: Optional[str] = None


class KnowledgeSearchTool:
    """Search internal cybersecurity knowledge base"""
    
    def __init__(self):
        """Initialize knowledge search tool"""
        # In production, this would connect to a vector database
        # For now, we'll use mock data
        self.knowledge_base = self._initialize_mock_knowledge()
        
        # Categories for filtering
        self.valid_categories = [
            "incident_response",
            "prevention", 
            "threat_intel",
            "compliance"
        ]
    
    def search(
        self,
        query: str,
        categories: Optional[List[str]] = None,
        limit: int = 10,
        include_metadata: bool = True
    ) -> KnowledgeSearchResponse:
        """
        Search internal knowledge base for cybersecurity documentation.
        
        Args:
            query: Search query
            categories: Filter by categories (incident_response, prevention, threat_intel, compliance)
            limit: Maximum results to return
            include_metadata: Include document metadata in results
            
        Returns:
            A KnowledgeSearchResponse object.
        """
        # Validate categories
        if categories:
            categories = [cat for cat in categories if cat in self.valid_categories]
        else:
            categories = self.valid_categories
        
        # Limit results
        limit = min(limit, 50)
        
        try:
            logger.info(f"Searching knowledge base for: {query}")
            
            # In production, this would be a vector similarity search
            results = self._mock_search(query, categories, limit)
            
            # Format results
            formatted_results = []
            for doc in results:
                metadata = None
                if include_metadata:
                    metadata = KnowledgeResultMetadata(
                        doc_id=doc["doc_id"],
                        last_updated=doc["last_updated"],
                        tags=doc.get("tags", []),
                        author=doc.get("author", "Security Team")
                    )
                
                result = KnowledgeResult(
                    title=doc["title"],
                    category=doc["category"],
                    summary=doc["summary"],
                    relevance_score=doc["score"],
                    metadata=metadata
                )
                formatted_results.append(result)
            
            return KnowledgeSearchResponse(
                query=query,
                categories_searched=categories,
                results=formatted_results,
                total_results=len(formatted_results)
            )
            
        except Exception as e:
            logger.error(f"Knowledge search error: {str(e)}")
            return KnowledgeSearchResponse(
                status="error",
                query=query,
                categories_searched=categories or [],
                results=[],
                total_results=0,
                error=str(e)
            )
    
    def _initialize_mock_knowledge(self) -> List[Dict[str, Any]]:
        """Initialize mock knowledge base for testing"""
        return [
            # Incident Response Documents
            {
                "doc_id": "ir_001",
                "title": "Ransomware Incident Response Playbook",
                "category": "incident_response",
                "summary": "Step-by-step guide for responding to ransomware attacks including isolation, analysis, and recovery procedures.",
                "content": "Full playbook content...",
                "tags": ["ransomware", "incident", "playbook"],
                "last_updated": "2024-01-15",
                "score": 0.95
            },
            {
                "doc_id": "ir_002",
                "title": "Data Breach Response Procedures",
                "category": "incident_response",
                "summary": "Comprehensive procedures for handling data breaches including legal notifications and forensics.",
                "tags": ["data breach", "incident", "forensics"],
                "last_updated": "2024-01-10",
                "score": 0.90
            },
            
            # Prevention Documents
            {
                "doc_id": "prev_001",
                "title": "Zero Trust Architecture Implementation Guide",
                "category": "prevention",
                "summary": "Complete guide for implementing zero trust security architecture in enterprise environments.",
                "tags": ["zero trust", "architecture", "security"],
                "last_updated": "2024-01-20",
                "score": 0.88
            },
            {
                "doc_id": "prev_002",
                "title": "Cloud Security Best Practices",
                "category": "prevention",
                "summary": "Security best practices for AWS, Azure, and GCP cloud environments.",
                "tags": ["cloud", "aws", "azure", "gcp"],
                "last_updated": "2024-01-18",
                "score": 0.85
            },
            
            # Threat Intelligence Documents
            {
                "doc_id": "ti_001",
                "title": "APT Groups Reference Guide",
                "category": "threat_intel",
                "summary": "Detailed profiles of known APT groups, their TTPs, and attribution indicators.",
                "tags": ["apt", "threat actors", "attribution"],
                "last_updated": "2024-01-12",
                "score": 0.92
            },
            {
                "doc_id": "ti_002",
                "title": "MITRE ATT&CK Mapping Procedures",
                "category": "threat_intel",
                "summary": "How to map observed behaviors to MITRE ATT&CK framework techniques.",
                "tags": ["mitre", "attack", "ttps"],
                "last_updated": "2024-01-08",
                "score": 0.87
            },
            
            # Compliance Documents
            {
                "doc_id": "comp_001",
                "title": "GDPR Compliance Checklist",
                "category": "compliance",
                "summary": "Complete checklist for GDPR compliance including data handling and breach procedures.",
                "tags": ["gdpr", "compliance", "privacy"],
                "last_updated": "2024-01-05",
                "score": 0.89
            },
            {
                "doc_id": "comp_002",
                "title": "HIPAA Security Rule Implementation",
                "category": "compliance",
                "summary": "Implementation guide for HIPAA security rule requirements in healthcare environments.",
                "tags": ["hipaa", "healthcare", "compliance"],
                "last_updated": "2024-01-03",
                "score": 0.86
            }
        ]
    
    def _mock_search(self, query: str, categories: List[str], limit: int) -> List[Dict[str, Any]]:
        """Mock search implementation"""
        # Simple keyword matching for mock
        query_lower = query.lower()
        results = []
        
        for doc in self.knowledge_base:
            # Check category
            if doc["category"] not in categories:
                continue
            
            # Simple relevance scoring based on keyword matches
            score = 0
            if query_lower in doc["title"].lower():
                score += 0.5
            if query_lower in doc["summary"].lower():
                score += 0.3
            for tag in doc.get("tags", []):
                if query_lower in tag.lower():
                    score += 0.2
            
            if score > 0:
                doc_copy = doc.copy()
                doc_copy["score"] = min(score, 1.0)
                results.append(doc_copy)
        
        # Sort by score and limit
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]


# Create singleton instance
knowledge_search_tool = KnowledgeSearchTool()


# Export function for easy use
def knowledge_search(**kwargs) -> Dict[str, Any]:
    """Knowledge search function that MCP servers will import"""
    response = knowledge_search_tool.search(**kwargs)
    return response.model_dump()