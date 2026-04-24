"""
SQLite state management for the Scanner Service.

Tracks dataset states, resources, and scan history to enable
change detection and avoid reprocessing unchanged data.
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .models import Dataset, Resource, DownloadStatus


class StateDB:
    """SQLite database for tracking scanner state."""
    
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS datasets (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        title TEXT,
        notes TEXT,
        organization_id TEXT,
        organization_name TEXT,
        organization_title TEXT,
        license_title TEXT,
        update_frequency TEXT,
        tags TEXT,
        metadata_created TEXT,
        metadata_modified TEXT,
        last_scanned_at TEXT,
        status TEXT DEFAULT 'active',
        created_at TEXT,
        updated_at TEXT
    );

    CREATE TABLE IF NOT EXISTS resources (
        id TEXT PRIMARY KEY,
        dataset_id TEXT NOT NULL,
        name TEXT,
        format TEXT,
        url TEXT,
        size INTEGER,
        last_modified TEXT,
        file_hash TEXT,
        storage_path TEXT,
        download_status TEXT DEFAULT 'pending',
        created_at TEXT,
        updated_at TEXT,
        FOREIGN KEY (dataset_id) REFERENCES datasets(id)
    );

    CREATE TABLE IF NOT EXISTS scan_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at TEXT,
        completed_at TEXT,
        datasets_scanned INTEGER DEFAULT 0,
        datasets_new INTEGER DEFAULT 0,
        datasets_updated INTEGER DEFAULT 0,
        datasets_unchanged INTEGER DEFAULT 0,
        errors TEXT
    );
    
    CREATE INDEX IF NOT EXISTS idx_resources_dataset_id ON resources(dataset_id);
    CREATE INDEX IF NOT EXISTS idx_datasets_metadata_modified ON datasets(metadata_modified);
    """
    
    def __init__(self, db_path: Path | str):
        """Initialize the state database."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.executescript(self.SCHEMA)
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def get_dataset(self, dataset_id: str) -> Optional[dict]:
        """Get a dataset by ID."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM datasets WHERE id = ?",
                (dataset_id,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    
    def get_dataset_metadata_modified(self, dataset_id: str) -> Optional[datetime]:
        """Get the metadata_modified timestamp for a dataset."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT metadata_modified FROM datasets WHERE id = ?",
                (dataset_id,)
            )
            row = cursor.fetchone()
            if row and row["metadata_modified"]:
                return datetime.fromisoformat(row["metadata_modified"])
            return None
    
    def save_dataset(self, dataset: Dataset) -> None:
        """Save or update a dataset in the database."""
        now = datetime.now(timezone.utc).isoformat()
        
        with self._get_connection() as conn:
            # Check if exists
            existing = self.get_dataset(dataset.id)
            
            if existing:
                # Update
                conn.execute("""
                    UPDATE datasets SET
                        name = ?,
                        title = ?,
                        notes = ?,
                        organization_id = ?,
                        organization_name = ?,
                        organization_title = ?,
                        license_title = ?,
                        update_frequency = ?,
                        tags = ?,
                        metadata_created = ?,
                        metadata_modified = ?,
                        last_scanned_at = ?,
                        status = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (
                    dataset.name,
                    dataset.title,
                    dataset.notes,
                    dataset.organization.id if dataset.organization else None,
                    dataset.organization.name if dataset.organization else None,
                    dataset.organization.title if dataset.organization else None,
                    dataset.license_title,
                    dataset.update_frequency,
                    json.dumps(dataset.tags),
                    dataset.metadata_created.isoformat() if dataset.metadata_created else None,
                    dataset.metadata_modified.isoformat() if dataset.metadata_modified else None,
                    now,
                    dataset.status,
                    now,
                    dataset.id,
                ))
            else:
                # Insert
                conn.execute("""
                    INSERT INTO datasets (
                        id, name, title, notes,
                        organization_id, organization_name, organization_title,
                        license_title, update_frequency, tags,
                        metadata_created, metadata_modified,
                        last_scanned_at, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    dataset.id,
                    dataset.name,
                    dataset.title,
                    dataset.notes,
                    dataset.organization.id if dataset.organization else None,
                    dataset.organization.name if dataset.organization else None,
                    dataset.organization.title if dataset.organization else None,
                    dataset.license_title,
                    dataset.update_frequency,
                    json.dumps(dataset.tags),
                    dataset.metadata_created.isoformat() if dataset.metadata_created else None,
                    dataset.metadata_modified.isoformat() if dataset.metadata_modified else None,
                    now,
                    dataset.status,
                    now,
                    now,
                ))
            
            conn.commit()
    
    def save_resource(self, dataset_id: str, resource: Resource) -> None:
        """Save or update a resource in the database."""
        now = datetime.now(timezone.utc).isoformat()
        
        with self._get_connection() as conn:
            # Check if exists
            cursor = conn.execute(
                "SELECT id FROM resources WHERE id = ?",
                (resource.id,)
            )
            existing = cursor.fetchone()
            
            if existing:
                # Update
                conn.execute("""
                    UPDATE resources SET
                        dataset_id = ?,
                        name = ?,
                        format = ?,
                        url = ?,
                        size = ?,
                        last_modified = ?,
                        file_hash = ?,
                        storage_path = ?,
                        download_status = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (
                    dataset_id,
                    resource.name,
                    resource.format,
                    resource.url,
                    resource.size,
                    resource.last_modified.isoformat() if resource.last_modified else None,
                    resource.file_hash,
                    resource.storage_path,
                    resource.download_status,
                    now,
                    resource.id,
                ))
            else:
                # Insert
                conn.execute("""
                    INSERT INTO resources (
                        id, dataset_id, name, format, url, size,
                        last_modified, file_hash, storage_path,
                        download_status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    resource.id,
                    dataset_id,
                    resource.name,
                    resource.format,
                    resource.url,
                    resource.size,
                    resource.last_modified.isoformat() if resource.last_modified else None,
                    resource.file_hash,
                    resource.storage_path,
                    resource.download_status,
                    now,
                    now,
                ))
            
            conn.commit()
    
    def get_resources_for_dataset(self, dataset_id: str) -> list[dict]:
        """Get all resources for a dataset."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM resources WHERE dataset_id = ?",
                (dataset_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def update_resource_status(
        self, 
        resource_id: str, 
        status: DownloadStatus,
        storage_path: Optional[str] = None,
        file_hash: Optional[str] = None,
    ) -> None:
        """Update the download status of a resource."""
        now = datetime.now(timezone.utc).isoformat()
        
        with self._get_connection() as conn:
            if storage_path and file_hash:
                conn.execute("""
                    UPDATE resources SET
                        download_status = ?,
                        storage_path = ?,
                        file_hash = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (status.value, storage_path, file_hash, now, resource_id))
            else:
                conn.execute("""
                    UPDATE resources SET
                        download_status = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (status.value, now, resource_id))
            
            conn.commit()
    
    def start_scan(self) -> int:
        """Record the start of a scan and return the scan ID."""
        now = datetime.now(timezone.utc).isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO scan_history (started_at) VALUES (?)",
                (now,)
            )
            conn.commit()
            return cursor.lastrowid
    
    def complete_scan(
        self,
        scan_id: int,
        datasets_scanned: int,
        datasets_new: int,
        datasets_updated: int,
        datasets_unchanged: int,
        errors: list[str],
    ) -> None:
        """Record the completion of a scan."""
        now = datetime.now(timezone.utc).isoformat()
        
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE scan_history SET
                    completed_at = ?,
                    datasets_scanned = ?,
                    datasets_new = ?,
                    datasets_updated = ?,
                    datasets_unchanged = ?,
                    errors = ?
                WHERE id = ?
            """, (
                now,
                datasets_scanned,
                datasets_new,
                datasets_updated,
                datasets_unchanged,
                json.dumps(errors),
                scan_id,
            ))
            conn.commit()
    
    def get_scan_history(self, limit: int = 10) -> list[dict]:
        """Get recent scan history."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM scan_history ORDER BY id DESC LIMIT ?",
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def get_all_dataset_ids(self) -> list[str]:
        """Get all tracked dataset IDs."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT id FROM datasets")
            return [row["id"] for row in cursor.fetchall()]
    
    def get_stats(self) -> dict:
        """Get database statistics."""
        with self._get_connection() as conn:
            datasets_count = conn.execute(
                "SELECT COUNT(*) FROM datasets"
            ).fetchone()[0]
            
            resources_count = conn.execute(
                "SELECT COUNT(*) FROM resources"
            ).fetchone()[0]
            
            completed_downloads = conn.execute(
                "SELECT COUNT(*) FROM resources WHERE download_status = 'completed'"
            ).fetchone()[0]
            
            return {
                "datasets_count": datasets_count,
                "resources_count": resources_count,
                "completed_downloads": completed_downloads,
            }

