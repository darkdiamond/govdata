"""Pydantic models for the artifacts the pipeline produces.

Per dataset, three artifacts land in `frontend/public/datasets/<id>/`:

    data.json         — DatasetMeta. Scanner-derived facts from CKAN
                        (license, resources, formats, …). Owned by the
                        publisher, sourced from Firestore `sources/<id>`.
    agent_data.json   — AgentData. Agent-derived judgments
                        (summary_he, dataset_kind, related_ids).
                        Sourced from Firestore `sources/<id>.agent_data`.
    content.html      — Body markup written by the agent. Synced via GCS.

`manifest.json` (consumed by home + category pages) is a merged view
(DatasetMeta + AgentData + computed `embedding` + `related_ids`).
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

DatasetKind = Literal[
    "map",          # geographic entities (e.g., antennas, vaccination centers)
    "timeseries",   # time-indexed measurements
    "registry",     # entity list (e.g., NGOs, licensed professionals)
    "rankings",     # ordered/scored entities
    "misc",         # fallback
]


class ResourceEntry(BaseModel):
    """A downloadable file on the dataset page's resources card."""
    model_config = ConfigDict(extra="ignore")

    url: str
    format: str = ""
    name: Optional[str] = None
    size_bytes: Optional[int] = None
    description: Optional[str] = None


class DatasetMeta(BaseModel):
    """Scanner-derived per-dataset metadata. Written to `data.json` by the
    publisher from the Firestore `sources/<id>` document.
    """
    model_config = ConfigDict(extra="ignore")

    id: str
    slug: str                                    # deterministic Hebrew→Latin slug
    title: str
    organization: Optional[str] = None           # human-readable ministry title
    organization_slug: Optional[str] = None      # stable key for /ministries/<slug>/
    tags_he: list[str] = Field(default_factory=list)
    primary_resource_id: Optional[str] = None
    formats: list[str] = Field(default_factory=list)
    metadata_modified: Optional[datetime] = None

    license: Optional[str] = None
    record_count: Optional[int] = None
    resources: list[ResourceEntry] = Field(default_factory=list)

    # When the agent last (re)built the page for this dataset. Used by the
    # frontend as the user-facing "עודכן" timestamp — `metadata_modified`
    # from CKAN gets bumped daily for auto-refreshed datasets and is too
    # noisy to surface directly.
    last_analyzed_at: Optional[datetime] = None

    version: int = 1


class AgentData(BaseModel):
    """Agent-derived per-dataset judgments. Written to `agent_data.json`
    by the publisher from the Firestore `sources/<id>.agent_data` field.

    `extra='allow'` so future agent fields can be added without breaking
    existing pages (e.g. `key_findings`, `quality_notes`).
    """
    model_config = ConfigDict(extra="allow")

    summary_he: str
    dataset_kind: DatasetKind
    related_ids: list[str] = Field(default_factory=list, max_length=5)

    version: int = 1


class ManifestEntry(BaseModel):
    """Merged per-dataset entry in `manifest.json` (home + category pages).

    Built by the publisher by merging `DatasetMeta` (scanner) + `AgentData`
    (agent) + controller-computed `embedding` + `related_ids`. Not stored —
    rebuilt on every publish.
    """
    model_config = ConfigDict(extra="ignore")

    # DatasetMeta fields
    id: str
    slug: str
    title: str
    organization: Optional[str] = None
    organization_slug: Optional[str] = None
    tags_he: list[str] = Field(default_factory=list)
    primary_resource_id: Optional[str] = None
    formats: list[str] = Field(default_factory=list)
    metadata_modified: Optional[datetime] = None
    license: Optional[str] = None
    record_count: Optional[int] = None
    resources: list[ResourceEntry] = Field(default_factory=list)
    last_analyzed_at: Optional[datetime] = None

    # AgentData fields (optional — a scanned-but-never-analyzed source has none)
    summary_he: Optional[str] = None
    dataset_kind: Optional[DatasetKind] = None

    # Publisher-computed
    related_ids: list[str] = Field(default_factory=list, max_length=5)
    embedding: Optional[list[float]] = None

    version: int = 1


class Manifest(BaseModel):
    """Aggregated manifest.json consumed by the Nuxt home + category pages."""
    version: int = 1
    generated_at: datetime
    datasets: list[ManifestEntry] = Field(default_factory=list)

    # Hebrew tag → ASCII slug. Used by the frontend to build /tags/<slug>/
    # URLs that survive `nuxt generate` on Windows/WSL (literal `%`-encoded
    # directories cannot be created on those filesystems). Built by the
    # publisher from the union of every entry's `tags_he`.
    tag_slugs: dict[str, str] = Field(default_factory=dict)
