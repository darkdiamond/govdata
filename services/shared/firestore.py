"""Firestore state store — shared between scanner + builder.

Collections:
    sources/{dataset_id}   — per-dataset state (CKAN fields + analyzer state)
    scan_runs/{run_id}     — one document per builder invocation

The client picks up credentials from `GOOGLE_APPLICATION_CREDENTIALS` or the
runtime's default service account. When `FIRESTORE_EMULATOR_HOST` is set,
the firestore SDK talks to the local emulator and the project ID can be any
string.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Iterator, Optional

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

SOURCES_COLL = "sources"
SCAN_RUNS_COLL = "scan_runs"


@dataclass
class SourceRecord:
    """In-memory view of a `sources/{id}` document."""

    id: str
    name: str = ""
    title: str = ""
    notes: Optional[str] = None
    organization: dict = field(default_factory=dict)
    license_title: Optional[str] = None
    update_frequency: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    resources: list[dict] = field(default_factory=list)
    metadata_created: Optional[datetime] = None
    metadata_modified: Optional[datetime] = None

    first_seen_at: Optional[datetime] = None
    last_scanned_at: Optional[datetime] = None
    change_status: str = "unchanged"

    last_analyzed_at: Optional[datetime] = None
    last_analyzed_version: int = 0
    analysis_status: str = "never"
    last_error: Optional[str] = None
    page_path: Optional[str] = None

    @classmethod
    def from_doc(cls, doc) -> "SourceRecord":
        data: dict[str, Any] = doc.to_dict() or {}
        return cls(
            id=doc.id,
            name=data.get("name", "") or "",
            title=data.get("title", "") or "",
            notes=data.get("notes"),
            organization=data.get("organization") or {},
            license_title=data.get("license_title"),
            update_frequency=data.get("update_frequency"),
            tags=data.get("tags") or [],
            resources=data.get("resources") or [],
            metadata_created=data.get("metadata_created"),
            metadata_modified=data.get("metadata_modified"),
            first_seen_at=data.get("first_seen_at"),
            last_scanned_at=data.get("last_scanned_at"),
            change_status=data.get("change_status", "unchanged"),
            last_analyzed_at=data.get("last_analyzed_at"),
            last_analyzed_version=int(data.get("last_analyzed_version") or 0),
            analysis_status=data.get("analysis_status", "never"),
            last_error=data.get("last_error"),
            page_path=data.get("page_path"),
        )


class FirestoreStateStore:
    """Thin wrapper around `google.cloud.firestore.Client` with the methods
    the scanner + builder need. Prefer this over raw `firestore.Client()` so
    that collection names and field names stay in one place.
    """

    def __init__(
        self,
        project_id: Optional[str] = None,
        database: str = "(default)",
        client: Optional[firestore.Client] = None,
    ):
        self.project_id = (
            project_id
            or os.getenv("FIRESTORE_PROJECT_ID")
            or os.getenv("GOOGLE_CLOUD_PROJECT")
            or "govdata-il"
        )
        self.database = database
        self.client = client or firestore.Client(project=self.project_id, database=database)

    # ---- Scanner surface -------------------------------------------------

    def get_dataset_metadata_modified(self, dataset_id: str) -> Optional[datetime]:
        snap = self.client.collection(SOURCES_COLL).document(dataset_id).get()
        if not snap.exists:
            return None
        return (snap.to_dict() or {}).get("metadata_modified")

    def save_dataset(self, dataset, change_status: str) -> None:
        """Upsert a `sources/{id}` document. Preserves analyzer fields."""
        now = datetime.now(timezone.utc)
        ref = self.client.collection(SOURCES_COLL).document(dataset.id)
        snap = ref.get()

        resources = [
            {
                "id": r.id,
                "name": r.name,
                "format": r.format,
                "url": r.url,
                "size": r.size,
                "last_modified": r.last_modified,
                "description": r.description,
            }
            for r in dataset.resources
        ]

        org: Optional[dict] = None
        if dataset.organization:
            org = {
                "id": dataset.organization.id,
                "name": dataset.organization.name,
                "title": dataset.organization.title,
                "logo_url": dataset.organization.logo_url,
            }

        payload: dict[str, Any] = {
            "id": dataset.id,
            "name": dataset.name,
            "title": dataset.title,
            "notes": dataset.notes,
            "organization": org,
            "license_title": dataset.license_title,
            "update_frequency": dataset.update_frequency,
            "tags": dataset.tags,
            "resources": resources,
            "metadata_created": dataset.metadata_created,
            "metadata_modified": dataset.metadata_modified,
            "last_scanned_at": now,
            "change_status": change_status,
        }

        if not snap.exists:
            payload["first_seen_at"] = now
            payload["analysis_status"] = "never"
            payload["last_analyzed_version"] = 0
            payload["last_analyzed_at"] = None
            payload["last_error"] = None
            payload["page_path"] = None

        ref.set(payload, merge=True)

    # ---- scan_runs -------------------------------------------------------

    def start_scan(self, mode: str = "scheduled") -> str:
        now = datetime.now(timezone.utc)
        ref = self.client.collection(SCAN_RUNS_COLL).document()
        ref.set(
            {
                "started_at": now,
                "mode": mode,
                "sources_seen": 0,
                "new": 0,
                "updated": 0,
                "unchanged": 0,
                "processed_source_ids": [],
                "processed_statuses": {},
            }
        )
        return ref.id

    def complete_scan(
        self,
        scan_id: str,
        *,
        sources_seen: int,
        new: int,
        updated: int,
        unchanged: int,
        processed_source_ids: Optional[list[str]] = None,
        processed_statuses: Optional[dict[str, str]] = None,
        errors: Optional[list[str]] = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        ref = self.client.collection(SCAN_RUNS_COLL).document(scan_id)
        snap = ref.get()
        started_at: Optional[datetime] = (
            (snap.to_dict() or {}).get("started_at") if snap.exists else None
        )
        duration_ms = (
            int((now - started_at).total_seconds() * 1000) if started_at else 0
        )
        ref.set(
            {
                "completed_at": now,
                "sources_seen": sources_seen,
                "new": new,
                "updated": updated,
                "unchanged": unchanged,
                "processed_source_ids": processed_source_ids or [],
                "processed_statuses": processed_statuses or {},
                "error": "\n".join(errors) if errors else None,
                "duration_ms": duration_ms,
            },
            merge=True,
        )

    def get_scan_history(self, limit: int = 10) -> list[dict]:
        query = (
            self.client.collection(SCAN_RUNS_COLL)
            .order_by("started_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )
        return [{"id": d.id, **(d.to_dict() or {})} for d in query.stream()]

    # ---- Builder surface -------------------------------------------------

    def get_source(self, dataset_id: str) -> Optional[SourceRecord]:
        snap = self.client.collection(SOURCES_COLL).document(dataset_id).get()
        if not snap.exists:
            return None
        return SourceRecord.from_doc(snap)

    def list_changed_sources(self, limit: int = 50) -> list[SourceRecord]:
        """Sources with `change_status` in {new, updated}, newest CKAN changes first."""
        query = (
            self.client.collection(SOURCES_COLL)
            .where(filter=FieldFilter("change_status", "in", ["new", "updated"]))
            .order_by("metadata_modified", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )
        return [SourceRecord.from_doc(d) for d in query.stream()]

    def list_never_analyzed(self, limit: int = 50) -> list[SourceRecord]:
        query = (
            self.client.collection(SOURCES_COLL)
            .where(filter=FieldFilter("analysis_status", "==", "never"))
            .order_by("metadata_modified", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )
        return [SourceRecord.from_doc(d) for d in query.stream()]

    def iter_succeeded_sources(self) -> Iterator[SourceRecord]:
        query = self.client.collection(SOURCES_COLL).where(
            filter=FieldFilter("analysis_status", "==", "succeeded")
        )
        for d in query.stream():
            yield SourceRecord.from_doc(d)

    def mark_analysis_pending(self, dataset_id: str) -> None:
        self.client.collection(SOURCES_COLL).document(dataset_id).set(
            {"analysis_status": "pending", "last_error": None},
            merge=True,
        )

    def mark_analysis_succeeded(
        self,
        dataset_id: str,
        page_path: str,
        manifest_entry: Optional[dict] = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        ref = self.client.collection(SOURCES_COLL).document(dataset_id)
        snap = ref.get()
        prev_version = int((snap.to_dict() or {}).get("last_analyzed_version") or 0)
        payload: dict[str, Any] = {
            "analysis_status": "succeeded",
            "last_analyzed_at": now,
            "last_analyzed_version": prev_version + 1,
            "page_path": page_path,
            "last_error": None,
        }
        if manifest_entry is not None:
            payload["manifest_entry"] = manifest_entry
        ref.set(payload, merge=True)

    def iter_manifest_entries(self) -> Iterator[dict]:
        """Yield each successful source's `manifest_entry` dict."""
        query = self.client.collection(SOURCES_COLL).where(
            filter=FieldFilter("analysis_status", "==", "succeeded")
        )
        for d in query.stream():
            data = d.to_dict() or {}
            entry = data.get("manifest_entry")
            if entry:
                yield entry

    def mark_analysis_failed(self, dataset_id: str, error: str) -> None:
        self.client.collection(SOURCES_COLL).document(dataset_id).set(
            {
                "analysis_status": "failed",
                "last_error": (error or "")[:1000],
            },
            merge=True,
        )

    # ---- Ops helpers -----------------------------------------------------

    def get_stats(self) -> dict[str, int]:
        counts = {
            "total": 0,
            "never": 0,
            "succeeded": 0,
            "failed": 0,
            "pending": 0,
        }
        for d in self.client.collection(SOURCES_COLL).stream():
            counts["total"] += 1
            status = (d.to_dict() or {}).get("analysis_status", "never")
            if status in counts:
                counts[status] += 1
        return counts

    def get_all_dataset_ids(self) -> list[str]:
        return [d.id for d in self.client.collection(SOURCES_COLL).stream()]
