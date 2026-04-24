"""
Resource downloader for the Scanner Service.

Downloads dataset resources to local storage with streaming
support and progress tracking.
"""

import asyncio
import csv
import hashlib
import json
from io import StringIO
from pathlib import Path
from typing import Optional, Callable
from urllib.parse import urlparse, unquote

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from .config import ScannerSettings, settings
from .models import Resource, DownloadStatus
from .state import StateDB


class DownloadError(Exception):
    """Exception raised for download errors."""
    pass


class SkippedFormatError(Exception):
    """Exception raised when a format is in the exclusion list."""
    pass


class InvalidContentError(Exception):
    """Exception raised when downloaded content doesn't match expected format."""
    pass


class ResourceDownloader:
    """Downloads resources with streaming and progress tracking."""
    
    def __init__(
        self, 
        config: Optional[ScannerSettings] = None,
        db: Optional[StateDB] = None,
    ):
        """
        Initialize the downloader.
        
        Args:
            config: Scanner settings.
            db: StateDB for updating download status.
        """
        self.config = config or settings
        self.db = db
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self) -> "ResourceDownloader":
        """Enter async context."""
        # Use browser-like headers to avoid bot protection
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,image/apng,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.9,he;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=10.0),
            follow_redirects=True,
            headers=headers,
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    def _get_filename_from_url(self, url: str, resource: Resource) -> str:
        """Extract filename from URL or resource metadata."""
        # Try to get from URL path
        parsed = urlparse(url)
        path = unquote(parsed.path)
        
        if path and "/" in path:
            filename = path.rsplit("/", 1)[-1]
            if filename and "." in filename:
                return filename
        
        # Fall back to resource name + format
        name = resource.name or resource.id
        ext = resource.format.lower() if resource.format else "dat"
        
        # Clean the name
        name = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)
        
        return f"{name}.{ext}"
    
    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute MD5 hash of a file."""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def _is_format_excluded(self, resource: Resource) -> bool:
        """Check if the resource format is in the exclusion list."""
        format_upper = resource.format.upper() if resource.format else ""
        return format_upper in self.config.EXCLUDED_FORMATS
    
    async def _download_via_datastore(
        self,
        resource: Resource,
        dataset_id: str,
        output_path: Path,
    ) -> bool:
        """
        Try to download resource via CKAN datastore API.
        
        This bypasses bot protection by using the official API.
        
        Returns:
            True if successful, False if datastore is not available.
        """
        if not self._client:
            return False
        
        # Only works for tabular data formats
        format_upper = resource.format.upper() if resource.format else ""
        if format_upper not in ("CSV", "JSON", "XLS", "XLSX"):
            return False
        
        try:
            # First, check if resource is in datastore with a small request
            check_url = f"{self.config.datastore_search_url}?resource_id={resource.id}&limit=1"
            response = await self._client.get(check_url)
            
            if response.status_code != 200:
                return False
            
            data = response.json()
            if not data.get("success"):
                return False
            
            # Get total count
            result = data.get("result", {})
            total = result.get("total", 0)
            
            if total == 0:
                return False
            
            # Download all records in batches
            all_records = []
            fields = None
            batch_size = 10000
            offset = 0
            
            while offset < total:
                batch_url = (
                    f"{self.config.datastore_search_url}"
                    f"?resource_id={resource.id}"
                    f"&limit={batch_size}&offset={offset}"
                )
                response = await self._client.get(batch_url)
                
                if response.status_code != 200:
                    break
                
                batch_data = response.json()
                if not batch_data.get("success"):
                    break
                
                batch_result = batch_data.get("result", {})
                records = batch_result.get("records", [])
                
                if not records:
                    break
                
                # Get field names from first batch
                if fields is None:
                    fields = [f["id"] for f in batch_result.get("fields", [])]
                    # Remove internal _id field
                    fields = [f for f in fields if not f.startswith("_")]
                
                all_records.extend(records)
                offset += batch_size
            
            if not all_records or not fields:
                return False
            
            # Write to CSV file
            with open(output_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(all_records)
            
            return True
            
        except Exception:
            return False
    
    def _validate_content(self, file_path: Path, resource: Resource) -> bool:
        """
        Validate that downloaded content matches expected format.
        
        Returns True if valid, False if content appears to be wrong format.
        """
        format_upper = resource.format.upper() if resource.format else ""
        
        # Read first bytes to check content
        try:
            with open(file_path, "rb") as f:
                header = f.read(512)
        except Exception:
            return True  # Can't read, assume valid
        
        # Check for HTML content (bot protection pages)
        html_signatures = [b"<html", b"<!DOCTYPE", b"<HTML", b"<!doctype"]
        if any(sig in header for sig in html_signatures):
            # This is HTML - only valid if format is HTML
            if format_upper not in ("HTML", "HTM"):
                return False
        
        # Basic format validation
        if format_upper == "CSV":
            # CSV should not start with HTML tags
            if header.startswith(b"<") or b"<script>" in header.lower():
                return False
        
        if format_upper == "JSON":
            # JSON should start with { or [
            stripped = header.lstrip()
            if stripped and stripped[0:1] not in (b"{", b"["):
                # Might be JSONL or have BOM, check further
                if b"<html" in header.lower():
                    return False
        
        if format_upper == "XML":
            # XML should start with <?xml or <
            stripped = header.lstrip()
            if stripped and not stripped.startswith(b"<"):
                return False
            if b"<html" in header.lower() and b"<?xml" not in header.lower():
                return False
        
        return True
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def download_resource(
        self,
        resource: Resource,
        dataset_id: str,
        on_progress: Optional[Callable[[int, int], None]] = None,
        validate_content: bool = True,
    ) -> Path:
        """
        Download a single resource.
        
        Args:
            resource: Resource to download.
            dataset_id: Parent dataset ID.
            on_progress: Optional callback(bytes_downloaded, total_bytes).
            validate_content: If True, validate content matches expected format.
        
        Returns:
            Path to the downloaded file.
        
        Raises:
            DownloadError: If download fails.
            SkippedFormatError: If format is excluded.
            InvalidContentError: If content doesn't match expected format.
        """
        if not self._client:
            raise RuntimeError("Downloader not initialized. Use 'async with' context.")
        
        # Check if format is excluded
        if self._is_format_excluded(resource):
            raise SkippedFormatError(
                f"Format '{resource.format}' is in exclusion list"
            )
        
        # Update status to downloading
        if self.db:
            self.db.update_resource_status(resource.id, DownloadStatus.DOWNLOADING)
        
        try:
            # Determine output path
            filename = self._get_filename_from_url(resource.url, resource)
            output_path = self.config.get_resource_download_path(
                dataset_id, 
                resource.id, 
                filename
            )
            
            # Try datastore API first (bypasses bot protection)
            datastore_success = await self._download_via_datastore(
                resource, dataset_id, output_path
            )
            
            if not datastore_success:
                # Fall back to direct URL download
                async with self._client.stream("GET", resource.url) as response:
                    response.raise_for_status()
                    
                    total_size = int(response.headers.get("content-length", 0))
                    downloaded = 0
                    
                    with open(output_path, "wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            if on_progress and total_size:
                                on_progress(downloaded, total_size)
                
                # Validate content if requested (only for direct downloads)
                if validate_content and not self._validate_content(output_path, resource):
                    # Delete the invalid file
                    output_path.unlink(missing_ok=True)
                    if self.db:
                        self.db.update_resource_status(resource.id, DownloadStatus.FAILED)
                    raise InvalidContentError(
                        f"Downloaded content is not valid {resource.format} "
                        f"(likely bot protection page)"
                    )
            
            # Compute file hash
            file_hash = self._compute_file_hash(output_path)
            
            # Update status to completed
            if self.db:
                self.db.update_resource_status(
                    resource.id,
                    DownloadStatus.COMPLETED,
                    storage_path=str(output_path),
                    file_hash=file_hash,
                )
            
            return output_path
            
        except (SkippedFormatError, InvalidContentError):
            raise
        except Exception as e:
            # Update status to failed
            if self.db:
                self.db.update_resource_status(resource.id, DownloadStatus.FAILED)
            raise DownloadError(f"Failed to download {resource.url}: {e}") from e
    
    async def download_resources(
        self,
        resources: list[Resource],
        dataset_id: str,
        on_resource_complete: Optional[Callable[[Resource, Path], None]] = None,
        on_resource_error: Optional[Callable[[Resource, Exception], None]] = None,
        on_resource_skipped: Optional[Callable[[Resource, str], None]] = None,
    ) -> dict[str, Path]:
        """
        Download multiple resources.
        
        Args:
            resources: List of resources to download.
            dataset_id: Parent dataset ID.
            on_resource_complete: Callback when a resource is downloaded.
            on_resource_error: Callback when a resource fails.
            on_resource_skipped: Callback when a resource is skipped (excluded format).
        
        Returns:
            Dictionary mapping resource_id to downloaded file path.
        """
        results = {}
        
        for resource in resources:
            try:
                path = await self.download_resource(resource, dataset_id)
                results[resource.id] = path
                
                if on_resource_complete:
                    on_resource_complete(resource, path)
            
            except SkippedFormatError as e:
                if on_resource_skipped:
                    on_resource_skipped(resource, str(e))
                    
            except Exception as e:
                if on_resource_error:
                    on_resource_error(resource, e)
        
        return results
    
    async def download_with_concurrency(
        self,
        resources: list[Resource],
        dataset_id: str,
        max_concurrent: int = 3,
    ) -> dict[str, Path]:
        """
        Download resources with limited concurrency.
        
        Args:
            resources: List of resources to download.
            dataset_id: Parent dataset ID.
            max_concurrent: Maximum concurrent downloads.
        
        Returns:
            Dictionary mapping resource_id to downloaded file path.
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        results = {}
        
        async def download_with_sem(resource: Resource) -> tuple[str, Optional[Path]]:
            async with semaphore:
                try:
                    path = await self.download_resource(resource, dataset_id)
                    return resource.id, path
                except Exception:
                    return resource.id, None
        
        tasks = [download_with_sem(r) for r in resources]
        completed = await asyncio.gather(*tasks)
        
        for resource_id, path in completed:
            if path:
                results[resource_id] = path
        
        return results

