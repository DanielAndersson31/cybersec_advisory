"""Core configuration management for Cybersecurity Advisory System"""

from typing import Optional
from pydantic import field_validator, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized configuration management for all application settings"""
    
    # Core Project Configuration
    project_name: str = Field(
        ...,
        env="PROJECT_NAME",
        description="Name of the application project"
    )
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
    tavily_api_key: Optional[SecretStr] = Field(
        None,
        env="TAVILY_API_KEY",
        description="Tavily API key for web search (optional)"
    )
    
    # Langfuse Observability (Phase 2)
    langfuse_public_key: str = Field(
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
    virustotal_api_key: Optional[SecretStr] = Field(
        None,
        env="VIRUSTOTAL_API_KEY",
        description="VirusTotal API key for threat analysis (optional)"
    )
    qdrant_api_key: Optional[SecretStr] = Field(
        None,
        env="QDRANT_API_KEY",
        description="QDrant API key for vector database (optional)"
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


# Global settings instance - single source of truth
settings = Settings()