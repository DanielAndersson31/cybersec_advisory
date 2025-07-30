"""Configuration package exports for easy importing"""

from config.settings import settings


# Main exports that other modules should use
__all__ = [
    # Core settings instance - single source of truth
    "settings",
]
