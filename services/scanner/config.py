"""
Configuration settings for the Scanner Service.

Uses pydantic-settings to load configuration from environment variables
and .env files.
"""

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class ScannerSettings(BaseSettings):
    """Scanner service configuration."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    # CKAN API Settings
    ckan_base_url: str = "https://data.gov.il/api/3/action"
    ckan_request_delay: float = 0.5  # Seconds between API requests
    ckan_timeout: int = 30  # Request timeout in seconds
    ckan_max_retries: int = 3  # Maximum retry attempts
    
    # Storage Paths
    data_dir: Path = Path("./data")
    downloads_dir: Path = Path("./data/downloads")
    db_path: Path = Path("./data/scanner.db")
    
    # Scanner Defaults
    default_limit: int = 5
    default_timeout: int = 30
    
    # Logging
    log_level: str = "INFO"

    # Page builder webhook (optional — when set, scanner POSTs dataset_id to this URL
    # on NEW/UPDATED events and skips it otherwise)
    page_builder_url: Optional[str] = None
    
    # Excluded file formats (hardcoded - won't be downloaded)
    # These are formats that are not useful for data analysis
    EXCLUDED_FORMATS: list[str] = [
        "PDF",      # PDF documents
        "DOC",      # Word documents
        "DOCX",     # Word documents
        "ZIP",      # Archives (might contain useful data but needs special handling)
        "RAR",      # Archives
        "7Z",       # Archives
        "EXE",      # Executables
        "MSI",      # Installers
    ]
    
    # Excluded dataset IDs (hardcoded - will be skipped entirely)
    # These are datasets that update too frequently or are not useful
    EXCLUDED_DATASET_IDS: list[str] = [
        "3dfc6b2a-bc1d-4770-8d5f-457ce50a73b3",  # מאגר טיסות - updates too frequently
    ]
    
    @property
    def package_list_url(self) -> str:
        """URL for listing all dataset IDs."""
        return f"{self.ckan_base_url}/package_list"
    
    @property
    def package_search_url(self) -> str:
        """URL for searching datasets."""
        return f"{self.ckan_base_url}/package_search"
    
    @property
    def package_show_url(self) -> str:
        """URL for getting dataset details."""
        return f"{self.ckan_base_url}/package_show"
    
    @property
    def datastore_search_url(self) -> str:
        """URL for datastore API (direct data access)."""
        return f"{self.ckan_base_url}/datastore_search"
    
    def get_datastore_dump_url(self, resource_id: str) -> str:
        """Get URL for downloading full resource as CSV via datastore."""
        return f"{self.ckan_base_url}/datastore_search?resource_id={resource_id}&limit=1000000"
    
    def ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
    
    def get_dataset_download_path(self, dataset_id: str) -> Path:
        """Get the download directory for a specific dataset."""
        path = self.downloads_dir / dataset_id
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    def get_resource_download_path(
        self, 
        dataset_id: str, 
        resource_id: str, 
        filename: Optional[str] = None
    ) -> Path:
        """Get the download path for a specific resource."""
        dataset_path = self.get_dataset_download_path(dataset_id)
        resource_path = dataset_path / resource_id
        resource_path.mkdir(parents=True, exist_ok=True)
        
        if filename:
            return resource_path / filename
        return resource_path


# Global settings instance
settings = ScannerSettings()

