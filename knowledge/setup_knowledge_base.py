import asyncio
import os
import pathlib
import logging
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from knowledge.vector_store import VectorStoreManager, Document

logger = logging.getLogger(__name__)

def load_and_split_docs(path: str) -> list:
    """Helper function to load from a directory and split docs."""
    loader = DirectoryLoader(path, glob="**/*.txt", loader_cls=TextLoader, show_progress=True)
    docs = loader.load()
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    chunks = text_splitter.split_documents(docs)
    logger.info(f"Loaded and split {len(docs)} documents into {len(chunks)} chunks from '{path}'.")
    return chunks

async def main():
    """
    Initializes and populates the knowledge base in Qdrant, creating a
    separate collection for each cybersecurity knowledge domain.
    """
    logger.info("Starting knowledge base setup process...")
    try:
        store_manager = VectorStoreManager()

        knowledge_base_path = pathlib.Path(__file__).parent.parent / "knowledge" / "domain_knowledge"

        # Map collection names to their source folder paths
        knowledge_domains = {
            "incident_response": knowledge_base_path / "incident_response_kb",
            "prevention": knowledge_base_path / "prevention_kb",
            "threat_intelligence": knowledge_base_path / "threat_intelligence_kb",
            "compliance": knowledge_base_path / "compliance_kb",
        }

        for name, path in knowledge_domains.items():
            if not path.exists() or not os.listdir(path):
                logger.warning(f"Skipping '{name}': Directory is empty or not found at '{path}'.")
                continue

            logger.info(f"Processing domain: '{name}'")
            
            # 1. Ensure the collection exists
            store_manager.create_collection_if_not_exists(name)

            # 2. Load and split documents using LangChain helpers
            langchain_docs = load_and_split_docs(str(path))
            
            if not langchain_docs:
                logger.warning(f"No documents found or loaded for domain '{name}'.")
                continue

            # 3. Convert to our structured Document class
            documents_to_upsert = [
                Document(content=doc.page_content, metadata=doc.metadata)
                for doc in langchain_docs
            ]

            # 4. Upsert the documents into the domain's collection
            store_manager.upsert_documents(name, documents_to_upsert)

        logger.info("Knowledge base setup completed successfully!")
    except Exception as e:
        logger.exception("A critical error occurred during the knowledge base setup.")
        # Re-raise the exception to ensure the script exits with an error code
        raise

if __name__ == "__main__":
    # If this script is the main entry point, it needs its own logging setup.
    # Otherwise, this part can be removed if it's only ever imported.
    from cybersec_team_ai.utils.logging_setup import setup_logging
    setup_logging()
    
    asyncio.run(main())