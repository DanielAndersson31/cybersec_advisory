import logging
from typing import List, Dict, Any
from .vector_store import VectorStoreManager

logger = logging.getLogger(__name__)

class KnowledgeRetriever:
    """
    Handles knowledge retrieval from the vector store for the agents,
    acting as a clean interface to the VectorStoreManager.
    """
    def __init__(self):
        """Initializes the retriever with a VectorStoreManager instance."""
        self.store_manager = VectorStoreManager()
        logger.info("KnowledgeRetriever initialized.")

    async def search(self, query: str, domain: str, k: int = 5) -> List[Dict[str, Any]]:
        """
        Performs a similarity search within a specific knowledge domain.

        Args:
            query: The search query string.
            domain: The knowledge domain to search in (e.g., 'incident_response').
            k: The number of top results to return.

        Returns:
            A list of dictionaries, each containing a search result.
        """
        logger.info(f"Performing search in domain '{domain}' for query: '{query[:50]}...'")
        return await self.store_manager.search(collection_name=domain, query=query, k=k)

knowledge_retriever = KnowledgeRetriever()