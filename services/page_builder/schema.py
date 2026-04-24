"""Pydantic models for the artifacts the agent + controller produce.

Per session the agent writes:
    /mnt/session/outputs/content.html  — body content (injected into <main>)
    /mnt/session/outputs/data.json     — ManifestEntry (agent-authored fields)

The controller then enriches `data.json` with computed fields (`embedding`,
`related_ids` if not set, etc.) and uploads both files plus a wrapped
`index.html` to `gs://<bucket>/datasets/<id>/`.
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


class ManifestEntry(BaseModel):
    """What `data.json` looks like after the agent writes it and the controller
    enriches it. Consumed by the home page + category pages + wrapper's related
    sidebar.
    """
    model_config = ConfigDict(extra="ignore")

    id: str
    slug: str                                    # URL slug for the dataset itself
    title: str
    organization: Optional[str] = None           # human-readable ministry title
    organization_slug: Optional[str] = None      # stable key for /ministries/<slug>/
    summary_he: Optional[str] = None
    tags_he: list[str] = Field(default_factory=list)
    primary_resource_id: Optional[str] = None
    formats: list[str] = Field(default_factory=list)
    metadata_modified: Optional[datetime] = None

    # Metadata + resources cards (rendered by frontend from data.json)
    license: Optional[str] = None
    record_count: Optional[int] = None
    resources: list[ResourceEntry] = Field(default_factory=list)

    # Agent-emitted classification + suggestions
    dataset_kind: Optional[DatasetKind] = None
    related_ids: list[str] = Field(default_factory=list, max_length=5)

    # Controller-computed (post-session)
    embedding: Optional[list[float]] = None      # Voyage vector, for similarity

    version: int = 1


class Manifest(BaseModel):
    """Aggregated manifest.json consumed by the Nuxt home + category pages."""
    version: int = 1
    generated_at: datetime
    datasets: list[ManifestEntry] = Field(default_factory=list)
