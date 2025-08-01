# mcp/clients/mcp_client.py
from mcp.config import get_all_server_urls, CLIENT_CONFIG

class MCPClient:
    def __init__(self):
        self.servers = get_all_server_urls()
        self.retry_config = CLIENT_CONFIG["retry"]