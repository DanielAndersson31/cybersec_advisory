import uuid
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any

from langchain_openai import OpenAIEmbeddings
from qdrant_client import QdrantClient, models

from config.settings import settings

logger = logging.getLogger(__name__)

@dataclass
class Document:
    """
    A structured data class for documents to be stored in the vector store.
    This aligns with best practices for data consistency.
    """
    content: str
    metadata: Dict[str, Any]
    doc_id: str = field(default_factory=lambda: str(uuid.uuid4()))


class VectorStoreManager:
    """
    Manages interactions with the Qdrant vector store using OpenAI's embedding model.
    It handles multiple collections, one for each cybersecurity domain.
    """
    def __init__(self):
        """Initializes the Qdrant client and the OpenAI embedding model."""
        self.client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.get_secret("qdrant_api_key")
        )
        
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-large", 
            openai_api_key=settings.get_secret("openai_api_key")
        )
        
        self.embedding_dim = 3072 # Dimension for text-embedding-3-large
        
        logger.info(f"VectorStoreManager initialized with OpenAI embeddings (dim: {self.embedding_dim})")

    def get_all_collection_names(self) -> List[str]:
        """Retrieve a list of all collection names from Qdrant."""
        try:
            collections_response = self.client.get_collections()
            return [col.name for col in collections_response.collections]
        except Exception as e:
            logger.exception(f"Failed to retrieve collection names: {e}")
            return []

    def create_collection_if_not_exists(self, collection_name: str):
        """
        Ensures a collection exists in Qdrant, creating it if necessary.

        Args:
            collection_name: The name for the collection.
        """
        vector_size = self.embedding_dim
        try:
            collections_response = self.client.get_collections()
            existing_collections = [col.name for col in collections_response.collections]
            if collection_name not in existing_collections:
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE)
                )
                logger.info(f"Collection '{collection_name}' created with vector size {vector_size}.")
            else:
                logger.info(f"Collection '{collection_name}' already exists.")
        except Exception as e:
            logger.exception(f"Failed to verify or create collection '{collection_name}': {e}")
            raise

    def upsert_documents(self, collection_name: str, documents: List[Document]):
        """
        Embeds and upserts a list of Document objects into a Qdrant collection.

        Args:
            collection_name: The name of the collection.
            documents: A list of Document objects to upsert.
        """
        if not documents:
            logger.warning(f"No documents to upsert for collection '{collection_name}'.")
            return

        try:
            contents = [doc.content for doc in documents]
            embedded_vectors = self.embeddings.embed_documents(contents)

            points = [
                models.PointStruct(
                    id=doc.doc_id,
                    vector=vector,
                    payload={"content": doc.content, "metadata": doc.metadata}
                )
                for doc, vector in zip(documents, embedded_vectors)
            ]

            self.client.upsert(collection_name=collection_name, points=points, wait=True)
            logger.info(f"Upserted {len(points)} documents to collection '{collection_name}'.")
        except Exception as e:
            logger.exception(f"Error upserting documents to '{collection_name}': {e}")
            raise

    async def search(self, collection_name: str, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """
        Performs a similarity search in a specified collection.

        Args:
            collection_name: The name of the collection to search.
            query: The text query to search for.
            k: The number of results to return.

        Returns:
            A list of search results with content, metadata, and score.
        """
        try:
            query_embedding = self.embeddings.embed_query(query)
            
            # Use self.client.search, which is the correct method for pre-computed vectors.
            hits = self.client.search(
                collection_name=collection_name,
                query_vector=query_embedding,
                limit=k,
                with_payload=True
            )
            
            # Process ScoredPoint objects from the search result
            formatted_results = []
            for hit in hits:
                payload = hit.payload or {}
                formatted_results.append({
                    "doc_id": hit.id,
                    "content": payload.get("content", ""),
                    "metadata": payload.get("metadata", {}),
                    "score": hit.score,
                })
            
            logger.info(f"Search in '{collection_name}' returned {len(formatted_results)} results.")
            return formatted_results
        except Exception as e:
            logger.exception(f"Search failed in collection '{collection_name}': {e}")
            return []