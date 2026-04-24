"""
Change detection — compares CKAN dataset metadata against Firestore state.

Resource-level diffing and downloads were removed when the scanner moved to
Firestore (the Managed Agent fetches resources in its own sandbox). This
module now only answers "is this dataset new / updated / unchanged?".
"""

from .models import Dataset, DatasetStatus
from .state import StateDB


class ChangeDetector:
    def __init__(self, db: StateDB):
        self.db = db

    def detect_status(self, dataset: Dataset, force: bool = False) -> DatasetStatus:
        stored_modified = self.db.get_dataset_metadata_modified(dataset.id)

        if stored_modified is None:
            return DatasetStatus.NEW
        if force:
            return DatasetStatus.UPDATED

        api_modified = dataset.metadata_modified
        if api_modified is None:
            return DatasetStatus.UNCHANGED
        if api_modified > stored_modified:
            return DatasetStatus.UPDATED
        return DatasetStatus.UNCHANGED
