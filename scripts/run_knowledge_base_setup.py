#!/usr/bin/env python3
"""
A simple runner script to execute the knowledge base setup process.
"""

import asyncio
import logging
import os
import sys

# Add the project root to the Python path to allow for absolute imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from knowledge.setup_knowledge_base import main as setup_kb_main
from config.settings import settings  # Import the central settings object

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


if __name__ == "__main__":
    logger.info("--- Starting Knowledge Base Setup ---")
    
    try:
        # Check for the key using the robust settings object
        settings.get_secret("openai_api_key")
        logger.info("OpenAI API key found.")
        
        asyncio.run(setup_kb_main())
        logger.info("--- Knowledge Base Setup Finished Successfully ---")
        
    except ValueError as e:
        # This catches the error from get_secret if the key is not found
        logger.error(f"FATAL: Configuration error - {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"--- Knowledge Base Setup Failed: {e} ---", exc_info=True)
        sys.exit(1)
