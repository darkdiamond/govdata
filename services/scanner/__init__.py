"""
GovData Scanner Service

Scans Israeli government datasets from data.gov.il CKAN API,
tracks state changes, and triggers appropriate downstream flows.
"""

from .models import Dataset, Resource, DatasetStatus, ScanResult, ScanSummary
from .client import CKANClient
from .config import ScannerSettings, settings
from .state import StateDB
from .detector import ChangeDetector
from .filters import DatasetFilter, create_filter
from .downloader import ResourceDownloader
from .main import Scanner, ScanCallbacks

__all__ = [
    "Dataset",
    "Resource", 
    "DatasetStatus",
    "ScanResult",
    "ScanSummary",
    "CKANClient",
    "ScannerSettings",
    "settings",
    "StateDB",
    "ChangeDetector",
    "DatasetFilter",
    "create_filter",
    "ResourceDownloader",
    "Scanner",
    "ScanCallbacks",
]

