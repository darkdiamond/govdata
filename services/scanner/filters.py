"""
Dataset filtering logic for the Scanner Service.

Provides flexible filtering of datasets based on various criteria
like name, format, organization, and tags.
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from .models import Dataset


@dataclass
class DatasetFilter:
    """
    Filter configuration for datasets.
    
    All filters are combined with AND logic - a dataset must match
    all specified filters to be included.
    """
    
    # Name filters
    name_contains: Optional[str] = None
    name_regex: Optional[str] = None
    
    # Resource format filters (e.g., CSV, JSON, XLSX)
    formats: list[str] = field(default_factory=list)
    
    # Organization filter
    organization: Optional[str] = None
    
    # Tag filters
    tags: list[str] = field(default_factory=list)
    
    # Exclude patterns
    exclude_name_contains: Optional[str] = None
    exclude_formats: list[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Normalize filter values."""
        # Normalize formats to uppercase
        self.formats = [f.upper() for f in self.formats]
        self.exclude_formats = [f.upper() for f in self.exclude_formats]
        
        # Compile regex if provided
        self._name_pattern = None
        if self.name_regex:
            self._name_pattern = re.compile(self.name_regex, re.IGNORECASE)
    
    def matches(self, dataset: Dataset) -> bool:
        """
        Check if a dataset matches all filter criteria.
        
        Args:
            dataset: Dataset to check.
        
        Returns:
            True if dataset matches all filters.
        """
        # Name contains filter
        if self.name_contains:
            if self.name_contains.lower() not in dataset.name.lower():
                if self.name_contains.lower() not in dataset.title.lower():
                    return False
        
        # Name regex filter
        if self._name_pattern:
            if not (self._name_pattern.search(dataset.name) or 
                    self._name_pattern.search(dataset.title)):
                return False
        
        # Exclude name contains
        if self.exclude_name_contains:
            if (self.exclude_name_contains.lower() in dataset.name.lower() or
                self.exclude_name_contains.lower() in dataset.title.lower()):
                return False
        
        # Format filter - dataset must have at least one resource with matching format
        if self.formats:
            resource_formats = {r.format.upper() for r in dataset.resources}
            if not resource_formats.intersection(self.formats):
                return False
        
        # Exclude formats - skip if dataset has resources in excluded formats
        if self.exclude_formats:
            resource_formats = {r.format.upper() for r in dataset.resources}
            if resource_formats.intersection(self.exclude_formats):
                return False
        
        # Organization filter
        if self.organization:
            if not dataset.organization:
                return False
            org_match = (
                self.organization.lower() in dataset.organization.name.lower() or
                self.organization.lower() in dataset.organization.title.lower()
            )
            if not org_match:
                return False
        
        # Tags filter - dataset must have all specified tags
        if self.tags:
            dataset_tags = {t.lower() for t in dataset.tags}
            required_tags = {t.lower() for t in self.tags}
            if not required_tags.issubset(dataset_tags):
                return False
        
        return True
    
    def filter_datasets(self, datasets: list[Dataset]) -> list[Dataset]:
        """
        Filter a list of datasets.
        
        Args:
            datasets: List of datasets to filter.
        
        Returns:
            Filtered list of datasets.
        """
        return [d for d in datasets if self.matches(d)]
    
    def filter_resources(self, dataset: Dataset) -> list:
        """
        Filter resources within a dataset based on format filters.
        
        Args:
            dataset: Dataset with resources.
        
        Returns:
            List of resources matching format filters.
        """
        if not self.formats and not self.exclude_formats:
            return list(dataset.resources)
        
        filtered = []
        for resource in dataset.resources:
            format_upper = resource.format.upper()
            
            # Check format inclusion
            if self.formats and format_upper not in self.formats:
                continue
            
            # Check format exclusion
            if self.exclude_formats and format_upper in self.exclude_formats:
                continue
            
            filtered.append(resource)
        
        return filtered
    
    def is_empty(self) -> bool:
        """Check if no filters are configured."""
        return (
            self.name_contains is None and
            self.name_regex is None and
            not self.formats and
            self.organization is None and
            not self.tags and
            self.exclude_name_contains is None and
            not self.exclude_formats
        )
    
    def describe(self) -> str:
        """Get a human-readable description of active filters."""
        parts = []
        
        if self.name_contains:
            parts.append(f"name contains '{self.name_contains}'")
        
        if self.name_regex:
            parts.append(f"name matches '{self.name_regex}'")
        
        if self.formats:
            parts.append(f"formats: {', '.join(self.formats)}")
        
        if self.organization:
            parts.append(f"organization: {self.organization}")
        
        if self.tags:
            parts.append(f"tags: {', '.join(self.tags)}")
        
        if self.exclude_name_contains:
            parts.append(f"excludes name '{self.exclude_name_contains}'")
        
        if self.exclude_formats:
            parts.append(f"excludes formats: {', '.join(self.exclude_formats)}")
        
        if not parts:
            return "No filters applied"
        
        return " AND ".join(parts)


def create_filter(
    name_contains: Optional[str] = None,
    name_regex: Optional[str] = None,
    formats: Optional[str] = None,
    organization: Optional[str] = None,
    tags: Optional[str] = None,
    exclude_name: Optional[str] = None,
    exclude_formats: Optional[str] = None,
) -> DatasetFilter:
    """
    Create a DatasetFilter from CLI-style arguments.
    
    Args:
        name_contains: Substring to find in dataset name/title.
        name_regex: Regex pattern to match dataset name/title.
        formats: Comma-separated list of formats (e.g., "csv,json").
        organization: Organization name substring.
        tags: Comma-separated list of required tags.
        exclude_name: Substring to exclude in dataset name/title.
        exclude_formats: Comma-separated list of formats to exclude.
    
    Returns:
        Configured DatasetFilter instance.
    """
    return DatasetFilter(
        name_contains=name_contains,
        name_regex=name_regex,
        formats=formats.split(",") if formats else [],
        organization=organization,
        tags=tags.split(",") if tags else [],
        exclude_name_contains=exclude_name,
        exclude_formats=exclude_formats.split(",") if exclude_formats else [],
    )

