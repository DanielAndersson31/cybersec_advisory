#!/usr/bin/env python3
"""
MCP Server Startup Script

Starts the cybersecurity MCP server with basic validation and monitoring.
"""

import sys
from pathlib import Path
from dotenv import load_dotenv

# 1. Add project root to Python's import path.
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 2. Explicitly load the .env file. This is crucial.
dotenv_path = project_root / '.env'
if dotenv_path.exists():
    load_dotenv(dotenv_path=dotenv_path)
    print(f"SUCCESS: Loaded environment variables from {dotenv_path}")
else:
    print(f"WARNING: .env file not found at {dotenv_path}. Server will likely fail.")

# 3. Now that the path and environment are set, we can import the server's main function.
from cybersec_mcp.cybersec_tools_server import main

# 4. Run the server directly in this process.
if __name__ == "__main__":
    main()
