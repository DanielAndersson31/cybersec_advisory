#!/usr/bin/env python3
"""
MCP Server Startup Script

Starts the cybersecurity MCP server with basic validation and monitoring.
"""

import sys
import subprocess
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Use existing logging setup from main.py pattern
try:
    from utils.logging import setup_logging
    setup_logging()
except ImportError:
    # Fallback if utils.logging not available
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

logger = logging.getLogger(__name__)


def validate_server():
    """Check if server file exists and config is valid"""
    server_file = project_root / "mcp" / "cybersec_tools_server.py"
    
    if not server_file.exists():
        logger.error(f"Server file not found: {server_file}")
        return False
        
    try:
        # Quick config validation
        from mcp.config import config
        config.validate_or_raise()
        logger.info("Configuration validated ✅")
        return True
    except Exception as e:
        logger.error(f"Configuration error: {e}")
        return False


def start_server():
    """Start the MCP server with monitoring"""
    logger.info("Starting Cybersecurity MCP Server...")
    
    server_script = project_root / "mcp" / "cybersec_tools_server.py"
    
    try:
        # Run server and wait for completion
        result = subprocess.run(
            [sys.executable, str(server_script)], 
            cwd=project_root,
            check=False  # Don't raise on non-zero exit
        )
        
        if result.returncode == 0:
            logger.info("Server stopped normally")
        else:
            logger.warning(f"Server exited with code: {result.returncode}")
            
    except KeyboardInterrupt:
        logger.info("Server stopped by user (Ctrl+C)")
    except FileNotFoundError:
        logger.error("Python interpreter not found")
    except Exception as e:
        logger.error(f"Failed to start server: {e}")


def main():
    """Main entry point"""
    logger.info("=" * 50)
    logger.info("🚀 Cybersecurity MCP Server")
    logger.info("=" * 50)
    
    # Validate before starting
    if not validate_server():
        logger.error("Validation failed. Exiting.")
        sys.exit(1)
    
    # Start the server
    start_server()
    
    logger.info("Server startup script finished")


if __name__ == "__main__":
    main()
