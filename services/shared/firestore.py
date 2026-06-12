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


def _count(query) -> int:
    """Run a Firestore .count() aggregation; return 0 on empty result."""
    result = query.count().get()
    if not result or not result[0]:
        return 0
    return int(result[0][0].value)


@dataclass
class SourceRecord:
    """In-memory view of a `sources/{id}` document."""

    id: str
    name: str = ""
    title: str = ""
    slug: str = ""
    notes: Optional[str] = None
    organization: dict = field(default_factory=dict)
    license_title: Optional[str] = None
    update_frequency: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    resources: list[dict] = field(default_factory=list)
    record_count: Optional[int] = None
    metadata_created: Optional[datetime] = None
    metadata_modified: Optional[datetime] = None

    first_seen_at: Optional[datetime] = None
    last_scanned_at: Optional[datetime] = None
    change_status: str = "unchanged"

    last_analyzed_at: Optional[datetime] = None
    # Source's metadata_modified at the moment of the last successful
    # analysis — i.e. the data vintage the agent's content is based on.
    # Distinct from `metadata_modified`, which is the *live* CKAN value
    # and gets overwritten on every scan. Captured by the builder via
    # `mark_analysis_succeeded`. The publisher falls back to
    # `min(metadata_modified, last_analyzed_at)` for legacy docs that
    # succeeded before this field existed.
    analyzed_metadata_modified: Optional[datetime] = None
    last_analyzed_version: int = 0
    analysis_status: str = "never"
    last_error: Optional[str] = None
    page_path: Optional[str] = None

    # Agent's per-dataset judgments (summary_he, dataset_kind, related_ids, …).
    # Set by the builder after a successful Managed Agents session; consumed
    # by the publisher to write `agent_data.json`.
    agent_data: Optional[dict] = None

    # Voyage embedding for related-dataset scoring. Cached here so the
    # publisher doesn't recompute on every run.
    embedding: Optional[list[float]] = None

    @classmethod
    def from_doc(cls, doc) -> "SourceRecord":
        data: dict[str, Any] = doc.to_dict() or {}
        return cls(
            id=doc.id,
            name=data.get("name", "") or "",
            title=data.get("title", "") or "",
            slug=data.get("slug", "") or "",
            notes=data.get("notes"),
            organization=data.get("organization") or {},
            license_title=data.get("license_title"),
            update_frequency=data.get("update_frequency"),
            tags=data.get("tags") or [],
            resources=data.get("resources") or [],
            record_count=data.get("record_count"),
            metadata_created=data.get("metadata_created"),
            metadata_modified=data.get("metadata_modified"),
            first_seen_at=data.get("first_seen_at"),
            last_scanned_at=data.get("last_scanned_at"),
            change_status=data.get("change_status", "unchanged"),
            last_analyzed_at=data.get("last_analyzed_at"),
            analyzed_metadata_modified=data.get("analyzed_metadata_modified"),
            last_analyzed_version=int(data.get("last_analyzed_version") or 0),
            analysis_status=data.get("analysis_status", "never"),
            last_error=data.get("last_error"),
            page_path=data.get("page_path"),
            agent_data=data.get("agent_data"),
            embedding=data.get("embedding"),
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
                "datastore_active": getattr(r, "datastore_active", False),
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
            "slug": getattr(dataset, "slug", "") or "",
            "notes": dataset.notes,
            "organization": org,
            "license_title": dataset.license_title,
            "update_frequency": dataset.update_frequency,
            "tags": dataset.tags,
            "resources": resources,
            "record_count": getattr(dataset, "record_count", None),
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
        started_at: Optional[datetime] = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        ref = self.client.collection(SCAN_RUNS_COLL).document(scan_id)
        if started_at is None:
            snap = ref.get()
            started_at = (
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

    def list_failed_retryable(
        self, limit: int = 50, max_attempts: int = 3
    ) -> list[SourceRecord]:
        """Failed sources still under the daily-retry budget, newest first.

        `failed_attempts < max_attempts` is filtered client-side: the field
        was introduced 2026-06 and older failed docs may lack it (treated
        as 1 — they failed at least once).
        """
        query = (
            self.client.collection(SOURCES_COLL)
            .where(filter=FieldFilter("analysis_status", "==", "failed"))
            .order_by("metadata_modified", direction=firestore.Query.DESCENDING)
            .limit(limit * 2)
        )
        out: list[SourceRecord] = []
        for d in query.stream():
            attempts = (d.to_dict() or {}).get("failed_attempts")
            if int(attempts if attempts is not None else 1) < max_attempts:
                out.append(SourceRecord.from_doc(d))
                if len(out) >= limit:
                    break
        return out

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
        analyzed_metadata_modified: Optional[datetime] = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        self.client.collection(SOURCES_COLL).document(dataset_id).set(
            {
                "analysis_status": "succeeded",
                "last_analyzed_at": now,
                "analyzed_metadata_modified": analyzed_metadata_modified,
                "last_analyzed_version": firestore.Increment(1),
                "page_path": page_path,
                "last_error": None,
                "failed_attempts": 0,
            },
            merge=True,
        )

    def set_agent_data(self, dataset_id: str, agent_data: dict) -> None:
        """Persist the agent's per-dataset judgments under `sources/<id>.agent_data`.

        Called by the builder after a successful Managed Agents session.
        Replaces the prior `manifest_entry` field entirely — scanner facts
        live alongside on the same doc, so there's no need to merge them.
        """
        self.client.collection(SOURCES_COLL).document(dataset_id).set(
            {"agent_data": agent_data}, merge=True
        )

    def set_session_usage(
        self,
        dataset_id: str,
        *,
        usage: dict,
        model_requests: int,
        elapsed_s: float,
        session_id: Optional[str] = None,
        agent_version: Optional[int] = None,
    ) -> None:
        """Persist per-session usage + cost so we can compare models/prompts.

        Stored under `sources/<id>.last_usage` — overwritten on every
        successful run. `actual_cost_usd` is the billed USD reported by
        OpenRouter usage accounting (None for runs without it).
        """
        now = datetime.now(timezone.utc)
        cost = usage.get("actual_cost_usd")
        self.client.collection(SOURCES_COLL).document(dataset_id).set(
            {
                "last_usage": {
                    "input_tokens": int(usage.get("input_tokens", 0)),
                    "output_tokens": int(usage.get("output_tokens", 0)),
                    "cache_read_input_tokens": int(
                        usage.get("cache_read_tokens")
                        or usage.get("cache_read_input_tokens")
                        or 0
                    ),
                    "model": usage.get("model"),
                    "actual_cost_usd": float(cost) if cost is not None else None,
                    "cost_source": usage.get("cost_source"),
                    "attempts": int(usage.get("attempts", 1)),
                    "model_requests": int(model_requests),
                    "elapsed_s": float(elapsed_s),
                    "session_id": session_id,
                    "agent_version": agent_version,
                    "recorded_at": now,
                },
            },
            merge=True,
        )

    def set_resource_datastore_flags(
        self, source_id: str, flags: dict[str, bool]
    ) -> bool:
        """Merge `datastore_active` flags into the doc's `resources` array,
        matched by resource id. Used by the one-shot backfill; the scanner
        writes the flag on every regular upsert going forward. Returns True
        if the doc was modified."""
        ref = self.client.collection(SOURCES_COLL).document(source_id)
        snap = ref.get()
        if not snap.exists:
            return False
        resources = (snap.to_dict() or {}).get("resources") or []
        changed = False
        for r in resources:
            rid = r.get("id")
            if rid in flags and r.get("datastore_active") != flags[rid]:
                r["datastore_active"] = flags[rid]
                changed = True
        if changed:
            ref.set({"resources": resources}, merge=True)
        return changed

    def set_embedding(self, dataset_id: str, embedding: list[float]) -> None:
        """Cache the Voyage embedding so the publisher doesn't recompute it."""
        self.client.collection(SOURCES_COLL).document(dataset_id).set(
            {"embedding": embedding}, merge=True
        )

    def mark_analysis_failed(self, dataset_id: str, error: str) -> None:
        # `failed_attempts` counts whole pipeline-run failures (each one
        # already burned SESSION_ATTEMPTS in-run retries). The selector
        # re-picks failed sources until this reaches 3, then parks them.
        self.client.collection(SOURCES_COLL).document(dataset_id).set(
            {
                "analysis_status": "failed",
                "last_error": (error or "")[:1000],
                "failed_attempts": firestore.Increment(1),
            },
            merge=True,
        )

    # ---- Ops helpers -----------------------------------------------------

    def get_stats(self) -> dict[str, int]:
        coll = self.client.collection(SOURCES_COLL)
        counts: dict[str, int] = {"total": _count(coll)}
        for status in ("never", "succeeded", "failed", "pending"):
            counts[status] = _count(
                coll.where(filter=FieldFilter("analysis_status", "==", status))
            )
        return counts

    def get_all_dataset_ids(self) -> list[str]:
        return [d.id for d in self.client.collection(SOURCES_COLL).stream()]
