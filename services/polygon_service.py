import logging
import requests
from fastapi import HTTPException, status
from typing import Dict, Any, Optional
import os

logger = logging.getLogger(__name__)

class PolygonService:
    POLYGON_BASE_URL = "https://api.polygon.io"
    POLYGON_API_KEY = os.environ.get("POLYGON_API_KEY")
    if not POLYGON_API_KEY:
        raise RuntimeError("POLYGON_API_KEY environment variable is not set.")

    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Helper to make requests to Polygon.io API."""
        if params is None:
            params = {}
        params["apiKey"] = self.POLYGON_API_KEY
        url = f"{self.POLYGON_BASE_URL}{endpoint}"

        try:
            response = requests.get(url, params=params, timeout=10)
            try:
                data = response.json()
            except ValueError:
                logger.error("Invalid JSON response from Polygon.io.")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invalid JSON response from Polygon.io.")

            if response.status_code >= 400:
                # If Polygon.io returns a JSON error, propagate its status/message
                detail = data.get("message", "Polygon.io API error.")
                status_val = data.get("status", "error")
                logger.warning(f"Polygon API error for {endpoint} with params {params}: {detail}")
                raise HTTPException(status_code=response.status_code, detail={"status": status_val, "message": detail})

            if data.get("status") == "ERROR" or data.get("status") == "NOT_FOUND":
                detail = data.get("message", "Data not found or API error.")
                logger.warning(f"Polygon API error for {endpoint} with params {params}: {detail}")
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"status": data.get("status"), "message": detail})
            if data.get("status") == "failed": # Specific for open-close endpoint
                logger.warning(f"Polygon API failed for {endpoint} with params {params}: {data.get('error')}")
                return {} # Return empty dict if data not available for specific date

            return data
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error from Polygon.io ({response.status_code}): {e}")
            raise HTTPException(status_code=response.status_code, detail=f"Polygon.io HTTP error: {e}")
        except requests.exceptions.ConnectionError:
            logger.error("Could not connect to Polygon.io API.")
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not connect to Polygon.io API.")
        except requests.exceptions.Timeout:
            logger.error("Polygon.io API request timed out.")
            raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Polygon.io API request timed out.")
        except requests.exceptions.RequestException as e:
            logger.error(f"An error occurred while fetching data from Polygon.io: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An error occurred with Polygon.io: {e}")

    async def get_daily_open_close(self, symbol: str, date_str: str) -> Dict[str, Any]:
        """Fetches daily open/close data for a stock from Polygon.io."""
        endpoint = f"/v1/open-close/{symbol}/{date_str}"
        logger.info(f"Fetching daily open/close for {symbol} on {date_str} from Polygon.io.")
        # Add 'adjusted': True to match Polygon.io example
        return self._make_request(endpoint, params={"adjusted": "true"})

    async def get_company_details(self, symbol: str) -> Dict[str, Any]:
        """Fetches company details (like name) for a stock from Polygon.io."""
        endpoint = f"/v3/reference/tickers/{symbol}"
        logger.info(f"Fetching company details for {symbol} from Polygon.io.")
        data = self._make_request(endpoint)
        return data.get("results", {}) # Company details are under 'results' key