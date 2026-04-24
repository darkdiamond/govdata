"""
CKAN API client for data.gov.il.

Provides async methods to interact with the Israeli government
open data portal API.
"""

import asyncio
from typing import Any, Optional

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from .config import ScannerSettings, settings
from .models import Dataset


class CKANError(Exception):
    """Exception raised for CKAN API errors."""
    pass


class CKANClient:
    """Async client for the CKAN API."""
    
    def __init__(self, config: Optional[ScannerSettings] = None):
        """Initialize the CKAN client."""
        self.config = config or settings
        self._client: Optional[httpx.AsyncClient] = None
        self._last_request_time: float = 0
    
    async def __aenter__(self) -> "CKANClient":
        """Enter async context."""
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.config.ckan_timeout),
            follow_redirects=True,
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def _rate_limit(self) -> None:
        """Apply rate limiting between requests."""
        current_time = asyncio.get_event_loop().time()
        elapsed = current_time - self._last_request_time
        delay = self.config.ckan_request_delay
        
        if elapsed < delay:
            await asyncio.sleep(delay - elapsed)
        
        self._last_request_time = asyncio.get_event_loop().time()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def _request(self, url: str, params: Optional[dict] = None) -> dict:
        """Make a rate-limited request to the CKAN API."""
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context.")
        
        await self._rate_limit()
        
        response = await self._client.get(url, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        if not data.get("success", False):
            error = data.get("error", {})
            raise CKANError(f"CKAN API error: {error}")
        
        return data.get("result", {})
    
    async def list_package_ids(self) -> list[str]:
        """
        List all dataset (package) IDs.
        
        Returns:
            List of dataset ID strings.
        """
        result = await self._request(self.config.package_list_url)
        return result if isinstance(result, list) else []
    
    async def search_packages(
        self,
        query: Optional[str] = None,
        rows: int = 100,
        start: int = 0,
        sort: str = "metadata_modified desc",
        fq: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Search for datasets.
        
        Args:
            query: Search query string
            rows: Number of results to return
            start: Offset for pagination
            sort: Sort order
            fq: Filter query (Solr syntax)
        
        Returns:
            Dictionary with 'count' and 'results' keys.
        """
        params = {
            "rows": rows,
            "start": start,
            "sort": sort,
        }
        
        if query:
            params["q"] = query
        
        if fq:
            params["fq"] = fq
        
        result = await self._request(self.config.package_search_url, params)
        
        return {
            "count": result.get("count", 0),
            "results": result.get("results", []),
        }
    
    async def get_package(self, package_id: str) -> Dataset:
        """
        Get full details for a specific dataset.
        
        Args:
            package_id: The dataset ID or name.
        
        Returns:
            Dataset model with all details.
        """
        result = await self._request(
            self.config.package_show_url,
            params={"id": package_id}
        )
        
        return Dataset.from_ckan_response(result)
    
    async def get_packages_batch(
        self, 
        package_ids: list[str],
        on_progress: Optional[callable] = None,
    ) -> list[Dataset]:
        """
        Get details for multiple datasets.
        
        Args:
            package_ids: List of dataset IDs to fetch.
            on_progress: Optional callback(current, total) for progress.
        
        Returns:
            List of Dataset models.
        """
        datasets = []
        total = len(package_ids)
        
        for i, package_id in enumerate(package_ids):
            try:
                dataset = await self.get_package(package_id)
                datasets.append(dataset)
            except Exception as e:
                # Log error but continue with other datasets
                print(f"Error fetching {package_id}: {e}")
            
            if on_progress:
                on_progress(i + 1, total)
        
        return datasets
    
    async def get_package_count(self) -> int:
        """
        Get the total number of datasets available.
        
        Returns:
            Total count of datasets.
        """
        result = await self.search_packages(rows=0)
        return result.get("count", 0)
    
    async def iter_all_packages(
        self,
        batch_size: int = 100,
        limit: Optional[int] = None,
        on_progress: Optional[callable] = None,
    ):
        """
        Iterate through all datasets with pagination.
        
        Args:
            batch_size: Number of datasets per API call.
            limit: Maximum number of datasets to return.
            on_progress: Optional callback(current, total) for progress.
        
        Yields:
            Dataset models one at a time.
        """
        start = 0
        fetched = 0
        total_count = await self.get_package_count()
        
        if limit:
            total_count = min(total_count, limit)
        
        while fetched < total_count:
            remaining = total_count - fetched
            rows = min(batch_size, remaining)
            
            result = await self.search_packages(rows=rows, start=start)
            
            for package_data in result.get("results", []):
                dataset = Dataset.from_ckan_response(package_data)
                yield dataset
                fetched += 1
                
                if on_progress:
                    on_progress(fetched, total_count)
                
                if limit and fetched >= limit:
                    return
            
            start += batch_size
            
            # Safety check to prevent infinite loops
            if not result.get("results"):
                break

