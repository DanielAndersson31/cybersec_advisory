"""
Tool to check for email exposure using XposedOrNot API.
"""

import logging
from typing import List, Optional
import httpx
from pydantic import BaseModel, ConfigDict
from langchain_core.tools import BaseTool
import asyncio

logger = logging.getLogger(__name__)


class ExposureDetails(BaseModel):
    """Details of a single exposure - simplified to match XposedOrNot API."""
    breach_name: str
    # Note: XposedOrNot api_v2 only provides breach names, not detailed metadata

class ExposureCheckResponse(BaseModel):
    """The structured response for an exposure check."""
    status: str = "success"
    query: str
    is_exposed: bool
    exposure_count: int
    exposures: List[ExposureDetails] = []
    breach_names: Optional[List[str]] = None  # Raw breach names from API
    error: Optional[str] = None
    message: Optional[str] = None


class ExposureCheckerTool(BaseTool):
    """
    Tool to check for email exposure using the XposedOrNot API.
    """
    name: str = "exposure_checker"
    description: str = "Check if an email address has been exposed in data breaches."
    base_url: str = "https://api.xposedornot.com/v1"
    client: httpx.AsyncClient = None

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    def __init__(self, **data):
        super().__init__(**data)
        """Initialize the XposedOrNot client."""
        self.client = httpx.AsyncClient(timeout=30.0)
        logger.info("ExposureCheckerTool initialized, using XposedOrNot API.")

    def _run(self, email: str) -> ExposureCheckResponse:
        """Checks a single email address against the XposedOrNot database."""
        return asyncio.run(self.check(email))

    async def _arun(self, email: str) -> ExposureCheckResponse:
        """Checks a single email address against the XposedOrNot database."""
        return await self.check(email)

    async def check(self, email: str) -> ExposureCheckResponse:
        """Checks a single email address against the XposedOrNot database."""
        try:
            logger.info(f"Making API request to: {self.base_url}/check-email/{email}")
            response = await self.client.get(f"{self.base_url}/check-email/{email}")
            
            logger.info(f"API Response Status: {response.status_code}")
            logger.info(f"API Response Headers: {dict(response.headers)}")
            
            response.raise_for_status()
            data = response.json()
            
            # Log the raw API response for debugging
            logger.info(f"Raw API Response: {data}")
            
            exposure_details = []
            breach_names_list = []
            
            # XposedOrNot api_v2 returns breaches as simple array of breach names
            if data.get("breaches"):
                breaches_list = data["breaches"]
                logger.info(f"Found breaches in response: {breaches_list}")
                
                # Handle if breaches is nested array: [["Breach1", "Breach2"]]
                if isinstance(breaches_list, list) and len(breaches_list) > 0:
                    if isinstance(breaches_list[0], list):
                        # Flatten nested array
                        breach_names_list = breaches_list[0]
                        logger.info(f"Flattened nested array: {breach_names_list}")
                    else:
                        breach_names_list = breaches_list
                        logger.info(f"Using direct array: {breach_names_list}")
                    
                    for breach_name in breach_names_list:
                        exposure_details.append(ExposureDetails(breach_name=str(breach_name)))
            else:
                logger.info("No 'breaches' key found in response")
            
            is_exposed = len(exposure_details) > 0
            message = f"Found {len(exposure_details)} breaches: {breach_names_list}" if is_exposed else "No breaches found"
            
            result = ExposureCheckResponse(
                query=email,
                is_exposed=is_exposed,
                exposure_count=len(exposure_details),
                exposures=exposure_details,
                breach_names=breach_names_list,
                message=message
            )
            
            logger.info(f"Final result: is_exposed={is_exposed}, count={len(exposure_details)}")
            return result
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP Status Error - Status: {e.response.status_code}")
            logger.error(f"HTTP Status Error - Response Text: {e.response.text}")
            
            if e.response.status_code == 404:
                logger.info(f"No breaches found for {email} (404 response)")
                return ExposureCheckResponse(
                    query=email, 
                    is_exposed=False, 
                    exposure_count=0,
                    message="No breaches found (404 response)"
                )
            
            error_msg = f"API Error {e.response.status_code}: {e.response.text}"
            logger.error(f"XON API error checking {email}: {error_msg}")
            return ExposureCheckResponse(
                status="error", 
                query=email, 
                is_exposed=False, 
                exposure_count=0, 
                error=error_msg
            )
        except Exception as e:
            logger.error(f"Unexpected error checking {email} with XON: {e}", exc_info=True)
            return ExposureCheckResponse(
                status="error", 
                query=email, 
                is_exposed=False, 
                exposure_count=0, 
                error=f"Unexpected error: {str(e)}"
            )

