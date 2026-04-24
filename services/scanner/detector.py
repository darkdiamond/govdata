"""
Change detection logic for the Scanner Service.

Compares datasets from the CKAN API against local state
to determine if action is needed.
"""

from datetime import datetime
from typing import Optional

from .models import Dataset, DatasetStatus
from .state import StateDB


class ChangeDetector:
    """Detects changes in datasets by comparing API data with local state."""
    
    def __init__(self, db: StateDB):
        """
        Initialize the change detector.
        
        Args:
            db: StateDB instance for querying local state.
        """
        self.db = db
    
    def detect_status(self, dataset: Dataset, force: bool = False) -> DatasetStatus:
        """
        Determine the status of a dataset.
        
        Args:
            dataset: Dataset from the CKAN API.
            force: If True, treat as UPDATED even if unchanged.
        
        Returns:
            DatasetStatus indicating NEW, UPDATED, or UNCHANGED.
        """
        # Get existing record from database
        stored_modified = self.db.get_dataset_metadata_modified(dataset.id)
        
        # Not in database -> NEW
        if stored_modified is None:
            return DatasetStatus.NEW
        
        # Force update requested
        if force:
            return DatasetStatus.UPDATED
        
        # Compare timestamps
        api_modified = dataset.metadata_modified
        
        if api_modified is None:
            # No timestamp from API, assume unchanged
            return DatasetStatus.UNCHANGED
        
        # Compare datetimes
        if api_modified > stored_modified:
            return DatasetStatus.UPDATED
        
        return DatasetStatus.UNCHANGED
    
    def detect_resource_changes(
        self, 
        dataset: Dataset,
    ) -> dict[str, DatasetStatus]:
        """
        Detect changes at the resource level.
        
        Args:
            dataset: Dataset with resources from the CKAN API.
        
        Returns:
            Dictionary mapping resource_id to DatasetStatus.
        """
        stored_resources = {
            r["id"]: r 
            for r in self.db.get_resources_for_dataset(dataset.id)
        }
        
        changes = {}
        
        for resource in dataset.resources:
            stored = stored_resources.get(resource.id)
            
            if stored is None:
                # New resource
                changes[resource.id] = DatasetStatus.NEW
            elif resource.last_modified:
                # Compare modification times
                stored_modified = stored.get("last_modified")
                if stored_modified:
                    stored_dt = datetime.fromisoformat(stored_modified)
                    if resource.last_modified > stored_dt:
                        changes[resource.id] = DatasetStatus.UPDATED
                    else:
                        changes[resource.id] = DatasetStatus.UNCHANGED
                else:
                    # No stored timestamp, check URL change
                    if resource.url != stored.get("url"):
                        changes[resource.id] = DatasetStatus.UPDATED
                    else:
                        changes[resource.id] = DatasetStatus.UNCHANGED
            else:
                # No API timestamp, check URL change
                if resource.url != stored.get("url"):
                    changes[resource.id] = DatasetStatus.UPDATED
                else:
                    changes[resource.id] = DatasetStatus.UNCHANGED
        
        return changes
    
    def get_resources_to_download(
        self, 
        dataset: Dataset,
        dataset_status: DatasetStatus,
        force: bool = False,
    ) -> list:
        """
        Get list of resources that need to be downloaded.
        
        Args:
            dataset: Dataset with resources from the CKAN API.
            dataset_status: Overall dataset status.
            force: If True, download all resources regardless of status.
        
        Returns:
            List of Resource objects that need downloading.
        """
        if dataset_status == DatasetStatus.NEW:
            # Download all resources for new datasets
            return list(dataset.resources)
        
        if dataset_status == DatasetStatus.UPDATED:
            if force:
                # Force mode: download all resources
                return list(dataset.resources)
            
            # Only download changed resources
            resource_changes = self.detect_resource_changes(dataset)
            return [
                r for r in dataset.resources
                if resource_changes.get(r.id) in (DatasetStatus.NEW, DatasetStatus.UPDATED)
            ]
        
        # UNCHANGED - no downloads needed
        return []

