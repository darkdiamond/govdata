"""
Pydantic models for the Scanner Service.

These models represent datasets, resources, and scan results
as returned from the CKAN API and stored locally.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class DatasetStatus(str, Enum):
    """Status of a dataset after change detection."""
    NEW = "new"              # Not in DB -> trigger new page flow
    UPDATED = "updated"      # metadata_modified changed -> trigger update flow
    UNCHANGED = "unchanged"  # No changes -> skip


class DownloadStatus(str, Enum):
    """Status of a resource download."""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"


class Organization(BaseModel):
    """Government organization that publishes datasets."""
    id: str
    name: str
    title: str
    logo_url: Optional[str] = None


class Resource(BaseModel):
    """A single resource (file) within a dataset."""
    id: str
    name: str
    format: str = ""
    url: str
    size: Optional[int] = None
    last_modified: Optional[datetime] = None
    description: Optional[str] = None
    
    # Local tracking fields (not from CKAN)
    file_hash: Optional[str] = None
    storage_path: Optional[str] = None
    download_status: DownloadStatus = DownloadStatus.PENDING

    class Config:
        use_enum_values = True


class Dataset(BaseModel):
    """A dataset (package) from the CKAN API."""
    id: str
    name: str
    title: str
    notes: Optional[str] = Field(default=None, description="Dataset description")
    organization: Optional[Organization] = None
    license_title: Optional[str] = None
    update_frequency: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    resources: list[Resource] = Field(default_factory=list)
    metadata_created: Optional[datetime] = None
    metadata_modified: Optional[datetime] = None
    
    # Local tracking fields
    last_scanned_at: Optional[datetime] = None
    status: str = "active"

    @classmethod
    def from_ckan_response(cls, data: dict) -> "Dataset":
        """Create a Dataset from CKAN API response."""
        # Parse organization
        org_data = data.get("organization")
        organization = None
        if org_data:
            organization = Organization(
                id=org_data.get("id", ""),
                name=org_data.get("name", ""),
                title=org_data.get("title", ""),
                logo_url=org_data.get("image_url"),
            )
        
        # Parse tags
        tags = [tag.get("name", "") for tag in data.get("tags", [])]
        
        # Parse resources
        resources = []
        for res_data in data.get("resources", []):
            resource = Resource(
                id=res_data.get("id", ""),
                name=res_data.get("name", ""),
                format=res_data.get("format", "").upper(),
                url=res_data.get("url", ""),
                size=res_data.get("size"),
                last_modified=_parse_datetime(res_data.get("last_modified")),
                description=res_data.get("description"),
            )
            resources.append(resource)
        
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            title=data.get("title", ""),
            notes=data.get("notes"),
            organization=organization,
            license_title=data.get("license_title"),
            update_frequency=data.get("update_frequency"),
            tags=tags,
            resources=resources,
            metadata_created=_parse_datetime(data.get("metadata_created")),
            metadata_modified=_parse_datetime(data.get("metadata_modified")),
        )


class ScanResult(BaseModel):
    """Result of scanning a single dataset."""
    dataset: Dataset
    status: DatasetStatus
    resources_downloaded: int = 0
    error: Optional[str] = None

    class Config:
        use_enum_values = True


class ScanSummary(BaseModel):
    """Summary of a complete scan run."""
    started_at: datetime
    completed_at: Optional[datetime] = None
    datasets_scanned: int = 0
    datasets_new: int = 0
    datasets_updated: int = 0
    datasets_unchanged: int = 0
    errors: list[str] = Field(default_factory=list)
    results: list[ScanResult] = Field(default_factory=list)


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse datetime string from CKAN API."""
    if not value:
        return None
    try:
        # CKAN uses ISO format: 2024-01-15T10:30:00
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None

