#!/usr/bin/env python3
"""
A robust runner script to execute the knowledge base setup process.
Supports flexible configuration via command line arguments.
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# Add the project root to the Python path to allow for absolute imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

# Must be after sys.path modification for proper module resolution
from knowledge.setup_knowledge_base import main as setup_kb_main
from config.settings import settings


def setup_logging(verbose: bool = False):
    """Configure logging based on verbosity level."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level, 
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Set up the cybersecurity knowledge base with document ingestion and vector indexing.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/run_knowledge_base_setup.py
  python scripts/run_knowledge_base_setup.py --knowledge-path ./my_docs
  python scripts/run_knowledge_base_setup.py --verbose --force-rebuild
        """
    )
    
    parser.add_argument(
        "--knowledge-path",
        type=str,
        default="knowledge/domain_knowledge",
        help="Path to the knowledge base directory (default: knowledge/domain_knowledge)"
    )
    
    parser.add_argument(
        "--force-rebuild",
        action="store_true",
        help="Force rebuild of existing collections"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose (DEBUG) logging"
    )
    
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check configuration and available documents, don't process"
    )
    
    return parser.parse_args()


def validate_knowledge_path(path: str) -> Path:
    """Validate and return the knowledge base path."""
    knowledge_path = Path(path)
    
    if not knowledge_path.exists():
        raise ValueError(f"Knowledge base path does not exist: {knowledge_path}")
    
    if not knowledge_path.is_dir():
        raise ValueError(f"Knowledge base path is not a directory: {knowledge_path}")
    
    # Check for at least one subdirectory (domain)
    subdirs = [p for p in knowledge_path.iterdir() if p.is_dir()]
    if not subdirs:
        raise ValueError(f"No domain subdirectories found in: {knowledge_path}")
    
    return knowledge_path


def main():
    """Main execution function."""
    args = parse_arguments()
    logger = setup_logging(args.verbose)
    
    logger.info("--- Starting Knowledge Base Setup ---")
    logger.info(f"Configuration: knowledge_path={args.knowledge_path}, force_rebuild={args.force_rebuild}")
    
    try:
        # Validate knowledge base path
        knowledge_path = validate_knowledge_path(args.knowledge_path)
        logger.info(f"Using knowledge base path: {knowledge_path.absolute()}")
        
        # Check for required API keys
        settings.get_secret("openai_api_key")
        logger.info("✓ OpenAI API key found")
        
        try:
            settings.get_secret("qdrant_api_key")
            logger.info("✓ Qdrant API key found")
        except ValueError:
            logger.warning("⚠ Qdrant API key not found - using local Qdrant instance")
        
        if args.check_only:
            logger.info("✓ Configuration check completed successfully")
            
            # List available domains
            subdirs = [p.name for p in knowledge_path.iterdir() if p.is_dir()]
            logger.info(f"Available knowledge domains: {', '.join(sorted(subdirs))}")
            
            # Count documents per domain
            for subdir in sorted(subdirs):
                domain_path = knowledge_path / subdir
                doc_files = [f for f in domain_path.rglob("*") if f.is_file() and f.suffix.lower() in ['.pdf', '.txt', '.md']]
                logger.info(f"  {subdir}: {len(doc_files)} documents")
            
            return
        
        # Run the actual setup process
        # Note: We might need to modify setup_kb_main to accept parameters
        asyncio.run(setup_kb_main())
        logger.info("--- Knowledge Base Setup Finished Successfully ---")
        
    except ValueError as e:
        logger.error(f"FATAL: Configuration error - {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"--- Knowledge Base Setup Failed: {e} ---", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
