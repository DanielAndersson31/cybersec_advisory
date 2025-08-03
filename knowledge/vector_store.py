import os
import uuid
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient, models

from config.settings import QDRANT_HOST, QDRANT_API_KEY, OPENAI_API_KEY

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
    Manages interactions with the Qdrant vector store using production-ready practices.
    It handles multiple collections, one for each cybersecurity domain.
    """

    def __init__(self):
        """Initializes the Qdrant client and the embedding model."""
        if not all([QDRANT_HOST, QDRANT_API_KEY, OPENAI_API_KEY]):
            logger.error("Required credentials for Qdrant or OpenAI are not set.")
            raise ValueError("Qdrant or OpenAI API credentials not found in environment.")

        self.client = QdrantClient(host=QDRANT_HOST, api_key=QDRANT_API_KEY)
        self.embeddings = OpenAIEmbeddings(model="text-embedding-3-small", openai_api_key=OPENAI_API_KEY)
        logger.info("VectorStoreManager initialized with Qdrant client and OpenAI embeddings.")

    def create_collection_if_not_exists(self, collection_name: str, vector_size: int = 1536):
        """
        Ensures a collection exists in Qdrant, creating it if necessary.

        Args:
            collection_name: The name for the collection.
            vector_size: The dimension of the vectors (1536 for OpenAI's text-embedding-3-small).
        """
        try:
            collections_response = self.client.get_collections()
            existing_collections = [col.name for col in collections_response.collections]
            if collection_name not in existing_collections:
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=models.VectorParams(
                        size=vector_size,
                        distance=models.Distance.COSINE,
                    ),
                )
                logger.info(f"Collection '{collection_name}' created successfully.")
            else:
                logger.info(f"Collection '{collection_name}' already exists.")
        except Exception as e:
            logger.exception(f"Failed to create or verify collection '{collection_name}': {e}")
            raise

    def upsert_documents(self, collection_name: str, documents: List[Document]):
        """
        Embeds and upserts a list of Document objects into a Qdrant collection.

        Args:
            collection_name: The name of the collection.
            documents: A list of Document objects to upsert.
        """
        if not documents:
            logger.warning(f"No documents provided to upsert for collection '{collection_name}'.")
            return

        try:
            contents = [doc.content for doc in documents]
            embedded_vectors = self.embeddings.embed_documents(contents)

            points = [
                models.PointStruct(
                    id=doc.doc_id,
                    vector=vector,
                    payload={"content": doc.content, "metadata": doc.metadata},
                )
                for doc, vector in zip(documents, embedded_vectors)
            ]

            self.client.upsert(collection_name=collection_name, points=points, wait=True)
            logger.info(f"Successfully upserted {len(points)} documents to collection '{collection_name}'.")
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
            search_results = self.client.search(
                collection_name=collection_name,
                query_vector=query_embedding,
                limit=k,
                with_payload=True,
            )
            
            formatted_results = [
                {
                    "doc_id": result.id,
                    "content": result.payload.get("content", ""),
                    "metadata": result.payload.get("metadata", {}),
                    "score": result.score,
                }
                for result in search_results
            ]
            logger.info(f"Search in '{collection_name}' returned {len(formatted_results)} results.")
            return formatted_results
        except Exception as e:
            logger.exception(f"Search failed in collection '{collection_name}': {e}")
            return []