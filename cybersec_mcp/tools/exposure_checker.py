"""
Tool to check for email exposure using XposedOrNot API.
"""

import logging
from typing import List, Optional
import httpx
from pydantic import ConfigDict
from langchain_core.tools import BaseTool
import asyncio

from .schemas import ExposureDetails, ExposureCheckResponse

logger = logging.getLogger(__name__)


class ExposureCheckerTool(BaseTool):
    """
    Tool to check for email exposure using the XposedOrNot API.
    
    ⚠️ PRIVACY WARNING: This tool sends email addresses to a third-party API (XposedOrNot).
    Only use for non-sensitive investigations. Do NOT use for internal corporate emails
    or sensitive personal information without proper authorization.
    """
    name: str = "exposure_checker"
    description: str = "Check if email has been exposed in breaches. ⚠️ PRIVACY: Sends email to 3rd-party API - only for non-sensitive investigations."
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
        logger.warning(f"⚠️ PRIVACY: Sending email '{email}' to third-party API (XposedOrNot). Ensure this is authorized for non-sensitive investigations only.")
        
        try:
            logger.info(f"Making API request to: {self.base_url}/check-email/{email}")
            response = await self.client.get(f"{self.base_url}/check-email/{email}")
            
            logger.info(f"API Response Status: {response.status_code}")
            logger.info(f"API Response Headers: {dict(response.headers)}")
            
            response.raise_for_status()
            data = response.json()
            
            logger.info(f"Raw API Response: {data}")
            
            exposure_details = []
            breach_names_list = []
            
            if data.get("breaches"):
                breaches_list = data["breaches"]
                logger.info(f"Found breaches in response: {breaches_list}")
                
                if isinstance(breaches_list, list) and len(breaches_list) > 0:
                    if isinstance(breaches_list[0], list):
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

