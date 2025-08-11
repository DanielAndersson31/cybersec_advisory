"""
Fallback strategies and error handling for the workflow.
Ensures graceful degradation when things go wrong.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ErrorHandler:
    """
    Handles errors and provides fallback responses.
    """
    
    def __init__(self):
        """Initialize error handler."""
        self.error_count = 0
        self.max_retries = 3
    
    def get_fallback_response(self, error: str) -> str:
        """
        Get a user-friendly fallback response for an error.
        
        Args:
            error: Error message
            
        Returns:
            User-friendly error response
        """
        logger.error(f"Generating fallback response for: {error}")
        
        # Don't expose internal errors to users
        if "rate limit" in error.lower():
            return (
                "I'm currently experiencing high demand. "
                "Please try again in a moment."
            )
        elif "timeout" in error.lower():
            return (
                "The analysis is taking longer than expected. "
                "Please try rephrasing your question or breaking it into smaller parts."
            )
        elif "mcp" in error.lower() or "tool" in error.lower():
            return (
                "I'm having trouble accessing some security tools at the moment. "
                "I'll provide analysis based on my expertise, but some real-time data may be unavailable."
            )
        else:
            return (
                "I apologize, but I encountered an issue processing your request. "
                "Please try rephrasing your question or contact support if the issue persists."
            )
    
    def should_retry(self, error_count: int, error: Optional[str]) -> bool:
        """
        Determine if the workflow should retry after an error.
        
        Args:
            error_count: Number of errors so far
            error: The error message
            
        Returns:
            True if should retry, False otherwise
        """
        if error_count >= self.max_retries:
            return False
        
        if error and "rate limit" in error.lower():
            return True  # Always retry rate limits
        
        if error and "timeout" in error.lower():
            return error_count < 2  # Only retry timeout once
        
        return error_count < self.max_retries
    
    def get_retry_strategy(self, error: str) -> dict:
        """
        Get retry strategy based on error type.
        
        Args:
            error: Error message
            
        Returns:
            Retry strategy configuration
        """
        if "rate limit" in error.lower():
            return {
                "wait_time": 5.0,
                "exponential_backoff": True,
                "max_wait": 30.0
            }
        elif "timeout" in error.lower():
            return {
                "wait_time": 2.0,
                "exponential_backoff": False,
                "max_wait": 5.0
            }
        else:
            return {
                "wait_time": 1.0,
                "exponential_backoff": False,
                "max_wait": 3.0
            }