import asyncio
import os
import pathlib
import logging
from langchain_community.document_loaders import DirectoryLoader, TextLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from knowledge.vector_store import VectorStoreManager, Document

logger = logging.getLogger(__name__)

def load_and_split_docs(path: str) -> list:
    """
    Loads TXT and PDF files from a directory, splits them into chunks.

    Args:
        path: The path to the directory containing documents.

    Returns:
        A list of LangChain Document chunks.
    """
    all_docs = []
    
    txt_loader = DirectoryLoader(path, glob="**/*.txt", loader_cls=TextLoader, show_progress=True, use_multithreading=True)
    all_docs.extend(txt_loader.load())

    pdf_loader = DirectoryLoader(path, glob="**/*.pdf", loader_cls=PyPDFLoader, show_progress=True, use_multithreading=True)
    all_docs.extend(pdf_loader.load())
    
    if not all_docs:
        return []

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    chunks = text_splitter.split_documents(all_docs)
    logger.info(f"Loaded and split {len(all_docs)} documents into {len(chunks)} chunks from '{path}'.")
    return chunks

async def main():
    """
    Initializes and populates the knowledge base in Qdrant. This script finds
    all supported documents in the domain knowledge folders, processes them,
    and creates a separate Qdrant collection for each domain.
    """
    logger.info("Starting knowledge base setup process...")
    try:
        store_manager = VectorStoreManager()

        knowledge_base_path = pathlib.Path(__file__).parent.parent / "knowledge" / "domain_knowledge"

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
            
            store_manager.create_collection_if_not_exists(name)

            langchain_docs = load_and_split_docs(str(path))
            
            if not langchain_docs:
                logger.warning(f"No processable documents (.txt, .pdf) found for domain '{name}'.")
                continue

            documents_to_upsert = [
                Document(content=doc.page_content, metadata=doc.metadata)
                for doc in langchain_docs
            ]

            store_manager.upsert_documents(name, documents_to_upsert)

        logger.info("Knowledge base setup completed successfully!")
    except Exception as e:
        logger.exception("A critical error occurred during the knowledge base setup.")
        raise

if __name__ == "__main__":    
    asyncio.run(main())