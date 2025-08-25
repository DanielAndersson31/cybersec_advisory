import uuid
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from fastembed import TextEmbedding
from qdrant_client import QdrantClient, models
from qdrant_client.models import Distance, VectorParams, PointStruct

from config.settings import settings

logger = logging.getLogger(__name__)

@dataclass
class Document:
    """
    A structured data class for documents to be stored in the vector store.
    """
    content: str
    metadata: Dict[str, Any]
    doc_id: str = field(default_factory=lambda: str(uuid.uuid4()))


class VectorStoreManager:
    """
    Manages interactions with the Qdrant vector store using FastEmbed.
    Optimized for cybersecurity knowledge retrieval.
    """
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        """
        Initializes the Qdrant client and the FastEmbed embedding model.
        
        Args:
            model_name: FastEmbed model to use (default: bge-small for speed/quality balance)
        """
        self.client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.get_secret("qdrant_api_key"),
            timeout=30  # Add timeout for production
        )
        
        # Initialize FastEmbed with caching for better performance
        self.embedding_model = TextEmbedding(
            model_name=model_name,
            cache_dir="./embedding_cache",  # Cache model files locally
            threads=4  # Use multiple threads for faster embedding
        )
        
        # Set dimensions based on model
        self.embedding_dim = 384 if "small" in model_name else 768
        
        logger.info(f"VectorStoreManager initialized with {model_name} (dim: {self.embedding_dim})")

    async def get_all_collection_names(self) -> List[str]:
        """Retrieve a list of all collection names from Qdrant."""
        try:
            collections_response = await self.client.get_collections()
            return [col.name for col in collections_response.collections]
        except Exception as e:
            logger.exception(f"Failed to retrieve collection names: {e}")
            return []
            
    def collection_exists(self, collection_name: str) -> bool:
        """Check if a collection exists in the database."""
        try:
            self.client.get_collection(collection_name=collection_name)
            return True
        except Exception:
            return False

    def create_collection_if_not_exists(self, collection_name: str):
        """
        Ensures a collection exists in Qdrant, creating it if necessary.
        
        Args:
            collection_name: The name for the collection
        """
        try:
            collections_response = self.client.get_collections()
            existing_collections = [col.name for col in collections_response.collections]
            
            if collection_name not in existing_collections:
                # Create with optimized settings for FastEmbed
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=self.embedding_dim,
                        distance=Distance.COSINE
                    ),
                    # Optimize for performance
                    optimizers_config=models.OptimizersConfigDiff(
                        indexing_threshold=10000,  # Start indexing after 10k vectors
                    ),
                    on_disk_payload=True  # Store payload on disk for large collections
                )
                logger.info(f"Collection '{collection_name}' created with vector size {self.embedding_dim}")
            else:
                logger.info(f"Collection '{collection_name}' already exists")
        except Exception as e:
            logger.exception(f"Failed to create collection '{collection_name}': {e}")
            raise

    def upsert_documents(self, collection_name: str, documents: List[Document], batch_size: int = 100):
        """
        Embeds and upserts documents with batching for better performance.
        
        Args:
            collection_name: The name of the collection
            documents: A list of Document objects to upsert
            batch_size: Number of documents to process at once
        """
        if not documents:
            logger.warning(f"No documents to upsert for collection '{collection_name}'")
            return

        try:
            total_processed = 0
            
            # Process in batches for better memory management
            for i in range(0, len(documents), batch_size):
                batch = documents[i:i + batch_size]
                
                # Prepare content with BGE prefix for optimal performance
                contents = [f"passage: {doc.content}" for doc in batch]
                
                # Embed batch (FastEmbed returns generator, convert to list)
                embedded_vectors = list(self.embedding_model.embed(contents))
                
                # Create points
                points = [
                    PointStruct(
                        id=doc.doc_id,
                        vector=vector.tolist() if hasattr(vector, 'tolist') else list(vector),
                        payload={
                            "content": doc.content,
                            "metadata": doc.metadata,
                            # Add useful fields for filtering
                            "doc_type": doc.metadata.get("type", "unknown"),
                            "timestamp": doc.metadata.get("timestamp", str(uuid.uuid4())),
                        }
                    )
                    for doc, vector in zip(batch, embedded_vectors)
                ]
                
                # Upsert batch
                self.client.upsert(
                    collection_name=collection_name,
                    points=points,
                    wait=True
                )
                
                total_processed += len(points)
                logger.info(f"Processed {total_processed}/{len(documents)} documents")
            
            logger.info(f"Successfully upserted {len(documents)} documents to '{collection_name}'")
            
        except Exception as e:
            logger.exception(f"Error upserting documents to '{collection_name}': {e}")
            raise

    async def search(
        self,
        collection_name: str,
        query: str,
        k: int = 5,
        score_threshold: float = 0.7,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Performs optimized similarity search with filtering.
        
        Args:
            collection_name: The name of the collection to search
            query: The text query to search for
            k: The number of results to return
            score_threshold: Minimum similarity score (0-1)
            filter_dict: Optional metadata filters
            
        Returns:
            A list of search results with content, metadata, and score
        """
        # Check if collection exists first
        if not self.collection_exists(collection_name):
            logger.info(f"Collection '{collection_name}' does not exist - knowledge base may not be populated yet")
            return []
        
        try:
            # Use query prefix for BGE models (critical for performance!)
            query_with_prefix = f"query: {query}"
            
            # Embed query manually for full control
            query_embedding = list(self.embedding_model.embed([query_with_prefix]))[0]
            
            # Search with embedded vector
            hits = self.client.search(
                collection_name=collection_name,
                query_vector=query_embedding.tolist() if hasattr(query_embedding, 'tolist') else list(query_embedding),
                query_filter=filter_dict,  # Add filtering if provided
                limit=k,
                score_threshold=score_threshold,  # Filter by minimum score
                with_payload=True
            )
            
            # Process results
            formatted_results = []
            for hit in hits:
                payload = hit.payload or {}
                formatted_results.append({
                    "doc_id": hit.id,
                    "content": payload.get("content", ""),
                    "metadata": payload.get("metadata", {}),
                    "score": hit.score,
                    "doc_type": payload.get("doc_type", "unknown")
                })
            
            logger.info(
                f"Search in '{collection_name}' for '{query[:50]}...' "
                f"returned {len(formatted_results)} results (threshold: {score_threshold})"
            )
            return formatted_results
            
        except Exception as e:
            # Handle missing collection gracefully
            if "doesn't exist" in str(e) or "Not found" in str(e):
                logger.info(f"Collection '{collection_name}' not found - knowledge base may not be populated yet")
                return []
            else:
                # Log other errors with full details
                logger.exception(f"Search failed in collection '{collection_name}': {e}")
                return []

    async def search_multiple_collections(
        self,
        query: str,
        collection_names: List[str],
        k_per_collection: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Search across multiple collections for comprehensive results.
        
        Args:
            query: The search query
            collection_names: List of collections to search
            k_per_collection: Results per collection
            
        Returns:
            Combined and ranked results from all collections
        """
        all_results = []
        
        for collection in collection_names:
            try:
                results = await self.search(
                    collection_name=collection,
                    query=query,
                    k=k_per_collection
                )
                # Add collection name to results
                for result in results:
                    result["collection"] = collection
                all_results.extend(results)
            except Exception as e:
                logger.error(f"Failed to search collection {collection}: {e}")
        
        # Sort by score and return top results
        all_results.sort(key=lambda x: x["score"], reverse=True)
        return all_results[:k_per_collection * len(collection_names)]