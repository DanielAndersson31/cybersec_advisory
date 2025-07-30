import os
from langfuse import Langfuse
from typing import Dict, Any, Optional
from config.settings import settings


class LangfuseSettings:
    """
    Langfuse settings class
    """
    def __init__(self):
        # Use settings from your settings.py file
        self.public_key = settings.LANGFUSE_PUBLIC_KEY
        self.secret_key = settings.LANGFUSE_SECRET_KEY
        self.host = settings.LANGFUSE_HOST
        
        # Validate that we have the required keys
        if not all([self.public_key, self.secret_key]):
            raise ValueError("Langfuse API keys not found in settings")
        
        # Initialize the Langfuse client
        self.client = Langfuse(
            public_key=self.public_key,
            secret_key=self.secret_key,
            host=self.host
        )