from fastmcp import FastMCP
from typing import Dict, any, List, Optional
from mcp.config import MCP_SERVERS
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

config = MCP_SERVERS["cybersec_tools"]

shared_metadata = {
    "name": config["name"],
    "description": config["description"],
    "version": "1.0.0",
    "author": "Cybersec AI",
    "contact": "info@cybersecai.com",
}

mcp = FastMCP(
    name=shared_metadata["name"],
    host=config["host"],
    port=config["port"],
    timeout=config["timeout"],
    description=shared_metadata["description"],
)

mcp.metadata = shared_metadata


@mcp.tool()
def web_search(query: str) -> str:
    """
    Search the web for information about the given query.
    """
    return "Searching the web for information about the given query."

@mcp.tool()
def knowledge_search(query: str) -> str:
    """
    Search the knowledge base for information about the given query.
    """
    return "Searching the knowledge base for information about the given query."
