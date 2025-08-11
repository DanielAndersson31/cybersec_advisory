"""Core configuration management for Cybersecurity Advisory System"""

from typing import Optional
from pydantic import field_validator, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Main settings class for the application, loaded from .env file.
    """
    # General settings
    APP_NAME: str = "Cybersecurity Multi-Agent Advisory System"
    environment: str = Field(
        ...,
        env="ENVIRONMENT",
        description="Runtime environment (development, staging, production)"
    )
    log_level: str = Field(
        ...,
        env="LOG_LEVEL",
        description="Logging level for the application"
    )
    default_model: str = Field(
        "gpt-4o",  # Sensible default
        env="DEFAULT_MODEL",
        description="Default language model for agents"
    )

    # Application Server Settings
    api_host: str = Field(
        ...,
        env="API_HOST",
        description="Host address for the API server"
    )
    api_port: int = Field(
        ...,
        env="API_PORT",
        ge=1024,
        le=65535,
        description="Port number for the API server"
    )
    
    # Database Configuration
    database_url: str = Field(
        ...,
        env="DATABASE_URL",
        min_length=1,
        description="Database connection URL for LangGraph checkpoints"
    )
    
    # LLM API Keys
    openai_api_key: SecretStr = Field(
        ...,
        env="OPENAI_API_KEY",
        description="OpenAI API key for LLM services"
    )
    tavily_api_key: SecretStr = Field(
        ...,
        env="TAVILY_API_KEY",
        description="Tavily API key for web search (optional)"
    )
    
    # Web Search Tool Configuration
    search_model_name: str = Field(
        default="gpt-3.5-turbo",
        env="SEARCH_MODEL_NAME",
        description="LLM model to use for query intent classification"
    )
    search_confidence_threshold: float = Field(
        default=0.7,
        env="SEARCH_CONFIDENCE_THRESHOLD",
        ge=0.0,
        le=1.0,
        description="Confidence threshold for activating cybersecurity search enhancements"
    )

    # Langfuse Observability (Phase 2)
    langfuse_public_key: SecretStr = Field(
        ...,
        env="LANGFUSE_PUBLIC_KEY",
        description="Langfuse public key for observability"
    )
    langfuse_secret_key: SecretStr = Field(
        ...,
        env="LANGFUSE_SECRET_KEY",
        description="Langfuse secret key for observability"
    )
    langfuse_host: str = Field(
        ...,
        env="LANGFUSE_HOST",
        description="Langfuse host URL"
    )
    
    # MCP Server Configuration (Phase 3)
    mcp_server_host: str = Field(
        ...,
        env="MCP_SERVER_HOST",
        description="MCP server host address"
    )
    mcp_server_port: int = Field(
        ...,
        env="MCP_SERVER_PORT",
        ge=1024,
        le=65535,
        description="MCP server port number"
    )
    
    # External API Keys (Optional)
    virustotal_api_key: SecretStr = Field(
        ...,
        env="VIRUSTOTAL_API_KEY",
        description="VirusTotal API key for threat analysis (optional)"
    )
    qdrant_url: str = Field(
        ...,
        env="QDRANT_URL",
        description="Full URL for Qdrant Cloud endpoint (e.g., https://...)"
    )
    qdrant_api_key: SecretStr = Field(
        ...,
        env="QDRANT_API_KEY",
        description="QDrant API key for vector database"
    )
    zoomeye_api_key: Optional[SecretStr] = Field(
        default=None,
        env="ZOOMEYE_API_KEY",
        description="ZoomEye API key for attack surface analysis (optional)"
    )
    otx_api_key: Optional[SecretStr] = Field(
        default=None,
        env="OTX_API_KEY",
        description="AlienVault OTX API key for threat feeds (optional)"
    )
    nist_api_key: Optional[SecretStr] = Field(
        default=None,
        env="NIST_API_KEY",
        description="NIST NVD API key for vulnerability search (optional)"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    @field_validator('log_level')
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in allowed_levels:
            raise ValueError(f'Log level must be one of {allowed_levels}')
        return v.upper()

    @field_validator('environment')
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed_envs = ['development', 'staging', 'production']
        if v.lower() not in allowed_envs:
            raise ValueError(f'Environment must be one of {allowed_envs}')
        return v.lower()

    def get_secret(self, key_name: str) -> str:
        """
        Safely retrieve a secret value, handling Pydantic's SecretStr.
        
        Args:
            key_name: The name of the setting attribute to retrieve.
            
        Returns:
            The secret as a plain string.
            
        Raises:
            ValueError: If the key is not found in the settings.
        """
        secret_value = getattr(self, key_name, None)
        if not secret_value:
            raise ValueError(f"Configuration key '{key_name}' not found or is empty.")
            
        if isinstance(secret_value, SecretStr):
            return secret_value.get_secret_value()
        return str(secret_value)


# Global settings instance - single source of truth
settings = Settings()