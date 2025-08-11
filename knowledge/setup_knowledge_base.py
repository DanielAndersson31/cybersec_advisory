import asyncio
import os
import pathlib
import logging
from langchain_community.document_loaders import (
    DirectoryLoader, TextLoader, PyPDFLoader, UnstructuredMarkdownLoader, UnstructuredWordDocumentLoader
)
from langchain_text_splitters import RecursiveCharacterTextSplitter

from knowledge.vector_store import VectorStoreManager, Document

logger = logging.getLogger(__name__)

def load_and_split_docs(path: str) -> list:
    """
    Loads all supported file types from a directory and splits them into chunks.
    Supported types: .txt, .pdf, .md, .docx
    """
    loaders = {
        ".txt": TextLoader,
        ".pdf": PyPDFLoader,
        ".md": UnstructuredMarkdownLoader,
        ".docx": UnstructuredWordDocumentLoader,
    }
    
    all_docs = []
    for ext, loader_cls in loaders.items():
        loader = DirectoryLoader(
            path, 
            glob=f"**/*{ext}", 
            loader_cls=loader_cls, 
            show_progress=True, 
            use_multithreading=True
        )
        all_docs.extend(loader.load())
    
    if not all_docs:
        return []

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    chunks = text_splitter.split_documents(all_docs)
    logger.info(f"Loaded and split {len(all_docs)} documents into {len(chunks)} chunks from '{path}'.")
    return chunks

async def main():
    """
    Initializes and populates the knowledge base in Qdrant. This script finds
    all subdirectories in the domain_knowledge folder, processes their documents,
    and creates a separate Qdrant collection for each domain.
    """
    logger.info("Starting knowledge base setup process...")
    try:
        store_manager = VectorStoreManager()
        knowledge_base_path = pathlib.Path(__file__).parent.parent / "knowledge" / "domain_knowledge"

        # Dynamically find all subdirectories to use as knowledge domains
        if not knowledge_base_path.exists():
            logger.error(f"Knowledge base directory not found at: {knowledge_base_path}")
            return

        domain_paths = [d for d in knowledge_base_path.iterdir() if d.is_dir()]

        for path in domain_paths:
            domain_name = path.name
            if not os.listdir(path):
                logger.warning(f"Skipping domain '{domain_name}': Directory is empty or not found at '{path}'.")
                continue

            logger.info(f"Processing domain: '{domain_name}'")
            
            store_manager.create_collection_if_not_exists(domain_name)

            langchain_docs = load_and_split_docs(str(path))
            
            if not langchain_docs:
                logger.warning(f"No processable documents found for domain '{domain_name}'.")
                continue

            documents_to_upsert = [
                Document(content=doc.page_content, metadata=doc.metadata)
                for doc in langchain_docs
            ]

            store_manager.upsert_documents(domain_name, documents_to_upsert)

        logger.info("Knowledge base setup completed successfully!")
    except Exception:
        logger.exception("A critical error occurred during the knowledge base setup.")
        raise

if __name__ == "__main__":    
    asyncio.run(main())