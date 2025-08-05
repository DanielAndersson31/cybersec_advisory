"""
Simple breach monitoring tool using the 'Have I Been Pwned' (HIBP) API.
"""

import os
import httpx
from typing import List, Optional
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)


# Pydantic Models
class BreachResult(BaseModel):
    """Details of a single data breach a credential appeared in."""
    name: str
    domain: str
    breach_date: str
    description: str
    data_classes: List[str] = []


class BreachMonitoringResponse(BaseModel):
    """Response model for the breach monitoring search."""
    status: str = "success"
    query_email: str
    is_breached: bool
    breach_count: int
    breaches: List[BreachResult]
    error: Optional[str] = None


class BreachMonitoringTool:
    """A tool to check for compromised credentials in data breaches."""
    
    def __init__(self):
        """Initialize with HIBP API details."""
        # HIBP API v3 requires an API key, passed in the headers.
        self.api_key = os.getenv("HIBP_API_KEY")
        self.base_url = "https://haveibeenpwned.com/api/v3"
        
    async def check_email(self, email: str) -> BreachMonitoringResponse:
        """
        Checks a single email address against the Have I Been Pwned database.
        
        Args:
            email: The email address to check.
            
        Returns:
            A BreachMonitoringResponse with details of any found breaches.
        """
        if not self.api_key:
            return BreachMonitoringResponse(
                status="error",
                query_email=email,
                is_breached=False,
                breach_count=0,
                breaches=[],
                error="HIBP_API_KEY environment variable not set."
            )

        headers = {
            "hibp-api-key": self.api_key,
            "user-agent": "Cybersecurity-Advisory-RAG" # HIBP requires a user-agent
        }
        url = f"{self.base_url}/breachedaccount/{email}"
        
        try:
            # Make the API request
            async with httpx.AsyncClient() as client:
                api_response = await client.get(url, headers=headers)
            
            # 404 means the email was not found in any breaches (a good thing)
            if api_response.status_code == 404:
                return BreachMonitoringResponse(
                    query_email=email,
                    is_breached=False,
                    breach_count=0,
                    breaches=[]
                )
            
            # 200 means breaches were found
            if api_response.status_code == 200:
                data = api_response.json()
                breach_results = [
                    BreachResult(
                        name=breach.get("Name", ""),
                        domain=breach.get("Domain", ""),
                        breach_date=breach.get("BreachDate", ""),
                        description=breach.get("Description", ""),
                        data_classes=breach.get("DataClasses", [])
                    ) for breach in data
                ]
                return BreachMonitoringResponse(
                    query_email=email,
                    is_breached=True,
                    breach_count=len(breach_results),
                    breaches=breach_results
                )
            
            # Handle other potential errors like rate limiting
            return BreachMonitoringResponse(
                status="error",
                query_email=email,
                is_breached=False,
                breach_count=0,
                breaches=[],
                error=f"HIBP API error: {api_response.status_code} - {api_response.text}"
            )

        except Exception as e:
            logger.error(f"Breach monitoring check error: {str(e)}")
            return BreachMonitoringResponse(
                status="error",
                query_email=email,
                is_breached=False,
                breach_count=0,
                breaches=[],
                error=str(e)
            )

# Create a singleton instance of the tool
breach_monitoring_tool = BreachMonitoringTool()


# Export function that the MCP server will import
async def check_breached_email(**kwargs) -> dict:
    """
    Checks if an email has been exposed in known data breaches.
    This function is the entry point for the MCP server.
    """
    # The primary argument should be 'email'
    email_to_check = kwargs.get("email")
    if not email_to_check:
        return {"status": "error", "error": "No email address provided."}
        
    response = await breach_monitoring_tool.check_email(email=email_to_check)
    return response.model_dump()
