"""
Configuration system for conversation management.
"""

import os


class ConversationConfig:
    """Configuration for conversation management behavior."""
    
    def __init__(self):
        """Initialize configuration with default values."""
        # Message and history settings
        self.max_messages_per_thread = 20
        self.auto_summarize_threshold = 50
        self.smart_truncation_enabled = True
        
        # Error handling and retry
        self.enable_auto_retry = True
        self.max_retry_attempts = 3
        self.retry_backoff_multiplier = 1.5
        self.retry_max_delay = 60.0
        
        # Thread management
        self.thread_cleanup_interval_hours = 24
        self.max_inactive_thread_age_hours = 72
        
        # Metrics and monitoring
        self.enable_metrics = True
        self.track_response_times = True
        self.track_agent_usage = True
        
        # LLM-based features
        self.enable_llm_summarization = True
        self.enable_smart_context_preservation = True
        self.summarization_model = "gpt-3.5-turbo"
        self.context_preservation_model = "gpt-3.5-turbo"
        
        # Privacy and security
        self.redact_pii = False  # Set to True for production
        self.max_retention_days = None  # None = no limit
        
        # Database and storage (disabled for localStorage approach)
        self.db_path = "./conversations.db"
        self.use_persistent_storage = False  # Force in-memory for localStorage
    
    @classmethod
    def from_env(cls):
        """Create config from environment variables."""
        config = cls()
        
        config.max_messages_per_thread = int(os.getenv('CONV_MAX_MESSAGES', '20'))
        config.enable_auto_retry = os.getenv('CONV_ENABLE_RETRY', 'true').lower() == 'true'
        config.max_retry_attempts = int(os.getenv('CONV_MAX_RETRIES', '3'))
        config.enable_metrics = os.getenv('CONV_ENABLE_METRICS', 'true').lower() == 'true'
        config.enable_llm_summarization = os.getenv('CONV_ENABLE_LLM_SUMMARY', 'true').lower() == 'true'
        config.redact_pii = os.getenv('CONV_REDACT_PII', 'false').lower() == 'true'
        config.db_path = os.getenv('CONV_DB_PATH', './conversations.db')
        
        return config


# For backward compatibility, provide a factory function
def get_default_config() -> ConversationConfig:
    """Factory function to create default configuration."""
    return ConversationConfig.from_env()
