import logging
from typing import List, Dict, Any, Optional
from .vector_store import VectorStoreManager
from config.settings import settings

logger = logging.getLogger(__name__)

class KnowledgeRetriever:
    """
    Handles knowledge retrieval from the vector store for the agents,
    acting as a clean interface to the VectorStoreManager.
    
    This class should be instantiated via dependency injection, not as a global singleton.
    """
    
    def __init__(self, qdrant_url: Optional[str] = None, qdrant_api_key: Optional[str] = None):
        """
        Initializes the retriever with a VectorStoreManager instance.
        
        Args:
            qdrant_url: URL for Qdrant instance (defaults to settings.qdrant_url)
            qdrant_api_key: API key for Qdrant (defaults to settings secret)
        """
        self.store_manager = VectorStoreManager(
            qdrant_url=qdrant_url or settings.qdrant_url,
            qdrant_api_key=qdrant_api_key or settings.get_secret("qdrant_api_key")
        )
        logger.info("KnowledgeRetriever initialized with dependency injection.")

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

    async def get_available_domains(self) -> List[str]:
        """
        Get list of all available knowledge domains (collection names).
        
        Returns:
            List of domain names available for searching
        """
        try:
            collections = await self.store_manager.async_client.get_collections()
            domain_names = [collection.name for collection in collections.collections]
            logger.debug(f"Available knowledge domains: {domain_names}")
            return domain_names
        except Exception as e:
            logger.error(f"Failed to get available domains: {e}")
            return []


def create_knowledge_retriever(qdrant_url: Optional[str] = None, qdrant_api_key: Optional[str] = None) -> KnowledgeRetriever:
    """
    Factory function to create a KnowledgeRetriever instance.
    Use this instead of the old global singleton pattern.
    """
    return KnowledgeRetriever(qdrant_url=qdrant_url, qdrant_api_key=qdrant_api_key)