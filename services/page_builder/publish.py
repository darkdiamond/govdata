"""Publisher — writes all per-dataset and aggregated frontend artifacts.

One process, one source of truth: the Firestore `sources/<id>` document.
For every source with `analysis_status == "succeeded"` we emit:

    <out_root>/datasets/<id>/data.json        — DatasetMeta (scanner facts)
    <out_root>/datasets/<id>/agent_data.json  — AgentData (agent judgments)

…and a single aggregated:

    <out_root>/data/manifest.json             — merged ManifestEntry list

`content.html` is not the publisher's concern — it's rsynced from GCS
staging by the surrounding Cloud Build step.

Running the publisher recomputes the Voyage embedding (when missing) and
the related-dataset scoring on every invocation, so manifest.json and the
per-dataset files always agree on what's "related" to what.

CLI:
    python -m services.page_builder.publish --from-firestore \
        --out frontend/public/
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from services.shared.firestore import FirestoreStateStore, SourceRecord
from services.shared.resources import pick_primary_resource_id

from .embeddings import voyage_enabled, embed, embedding_input
from .related import top_related
from .schema import (
    AgentData,
    DatasetMeta,
    Manifest,
    ManifestEntry,
    ResourceEntry,
)

log = logging.getLogger(__name__)


# ---- record assembly --------------------------------------------------------

def _resources_from_source(src: SourceRecord) -> list[ResourceEntry]:
    return [
        ResourceEntry(
            url=r["url"],
            format=(r.get("format") or "").upper(),
            name=r.get("name"),
            size_bytes=r.get("size"),
            description=r.get("description"),
        )
        for r in src.resources
        if r.get("url")
    ]


def _formats_from_resources(resources: Iterable[ResourceEntry]) -> list[str]:
    seen: set[str] = set()
    for r in resources:
        f = (r.format or "").upper()
        if f:
            seen.add(f)
    return sorted(seen)


def dataset_meta_from_source(src: SourceRecord) -> DatasetMeta:
    """Build the scanner-derived `data.json` shape from a Firestore source doc."""
    resources = _resources_from_source(src)
    # Pass `analyzed_metadata_modified` through verbatim. Legacy sources
    # (analyzed before the pipeline started snapshotting it) leave this
    # None — the frontend then falls back to `last_analyzed_at` for the
    # "המידע נכון ל-" display and suppresses the "מקור עודכן מאז" icon,
    # since we have no honest snapshot to compare against.
    return DatasetMeta(
        id=src.id,
        slug=src.slug or src.id,
        title=src.title,
        organization=(src.organization or {}).get("title") or None,
        organization_slug=(src.organization or {}).get("name") or None,
        tags_he=list(src.tags or []),
        primary_resource_id=pick_primary_resource_id(src.resources),
        formats=_formats_from_resources(resources),
        metadata_modified=src.metadata_modified,
        license=src.license_title,
        record_count=src.record_count,
        resources=resources,
        notes=src.notes,
        last_analyzed_at=src.last_analyzed_at,
        analyzed_metadata_modified=src.analyzed_metadata_modified,
    )


def agent_data_from_source(src: SourceRecord) -> Optional[AgentData]:
    """Validate and return `AgentData`, or None if the source has none yet."""
    if not src.agent_data:
        return None
    try:
        return AgentData.model_validate(src.agent_data)
    except Exception as e:
        log.warning("malformed agent_data for %s: %s", src.id, e)
        return None


_TAG_URL_UNSAFE = re.compile(r"[\s/?#&]+")


def _build_tag_slugs(entries: Iterable[ManifestEntry]) -> dict[str, str]:
    """Map each Hebrew tag in any entry's `tags_he` or `suggested_tags`
    to a URL-safe slug that keeps the Hebrew characters.

    Whitespace runs and URL-reserved chars (`/?#&`) collapse to `-`. The
    output is decoded Unicode (no percent-encoding) — Nitro writes those
    as native Unicode directory names during `nuxt generate`, and the
    link side encodes for the wire. Iterates in sorted order so the
    output is stable across runs; on slug collision appends a short
    sha1 suffix to disambiguate deterministically.
    """
    all_tags = sorted({
        t
        for e in entries
        for t in (e.tags_he or []) + (e.suggested_tags or [])
    })
    seen: dict[str, str] = {}        # url-slug -> the Hebrew tag that owns it
    out: dict[str, str] = {}
    for tag in all_tags:
        slug = _TAG_URL_UNSAFE.sub("-", tag).strip("-")
        if not slug:
            slug = hashlib.sha1(tag.encode("utf-8")).hexdigest()[:8]
        if slug in seen and seen[slug] != tag:
            digest = hashlib.sha1(tag.encode("utf-8")).hexdigest()[:6]
            slug = f"{slug}-{digest}"
        seen[slug] = tag
        out[tag] = slug
    return out


def _merged_entry(
    meta: DatasetMeta,
    agent: Optional[AgentData],
    embedding: Optional[list[float]],
) -> ManifestEntry:
    return ManifestEntry(
        **meta.model_dump(),
        summary_he=agent.summary_he if agent else None,
        dataset_kind=agent.dataset_kind if agent else None,
        temporal_coverage=agent.temporal_coverage if agent else None,
        spatial_coverage=agent.spatial_coverage if agent else None,
        suggested_tags=list(agent.suggested_tags) if agent else [],
        related_ids=list(agent.related_ids) if agent else [],
        embedding=embedding,
    )


# ---- file writes ------------------------------------------------------------

def _write_json(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)


def _write_dataset_meta(out_root: Path, meta: DatasetMeta) -> Path:
    target = out_root / "datasets" / meta.id / "data.json"
    body = meta.model_dump_json(exclude_none=True, indent=2).encode("utf-8")
    _write_json(target, body)
    return target


def _write_agent_data(out_root: Path, dataset_id: str, agent: AgentData) -> Path:
    target = out_root / "datasets" / dataset_id / "agent_data.json"
    body = agent.model_dump_json(exclude_none=True, indent=2).encode("utf-8")
    _write_json(target, body)
    return target


def _write_manifest(out_root: Path, manifest: Manifest) -> Path:
    target = out_root / "data" / "manifest.json"
    body = manifest.model_dump_json(exclude_none=True, indent=2).encode("utf-8")
    _write_json(target, body)
    return target


# ---- top-level orchestration ------------------------------------------------

def publish(
    out_root: Path,
    *,
    store: Optional[FirestoreStateStore] = None,
) -> dict:
    """Emit data.json + agent_data.json for each succeeded source and the
    merged manifest.json. Returns a small summary dict.
    """
    store = store or FirestoreStateStore()

    # First pass: load every successful source, build the un-related shape,
    # ensure each has an embedding cached on its doc.
    sources: list[SourceRecord] = list(store.iter_succeeded_sources())
    log.info("publish: %d succeeded source(s)", len(sources))

    metas: dict[str, DatasetMeta] = {}
    agents: dict[str, Optional[AgentData]] = {}
    embeddings: dict[str, Optional[list[float]]] = {}

    voyage_on = voyage_enabled()
    if not voyage_on:
        log.info("VOYAGE_ENABLED=false — skipping embedding + cosine path")

    for src in sources:
        meta = dataset_meta_from_source(src)
        agent = agent_data_from_source(src)
        metas[src.id] = meta
        agents[src.id] = agent

        if not voyage_on:
            embeddings[src.id] = None
            continue

        emb = src.embedding
        if emb is None and agent is not None:
            text = embedding_input(
                meta.title, agent.summary_he, meta.organization, meta.tags_he
            )
            emb = embed(text)
            if emb is not None:
                store.set_embedding(src.id, emb)
        embeddings[src.id] = emb

    # Second pass: compute related_ids over the full corpus. We build an
    # interim ManifestEntry for each so `top_related()` can use embeddings
    # + ministry + tags. The agent's own `related_ids` (if any) feed the
    # AGENT_SUGGESTED_WEIGHT signal inside top_related.
    interim: dict[str, ManifestEntry] = {
        sid: _merged_entry(metas[sid], agents[sid], embeddings[sid])
        for sid in metas
    }
    related_by_id: dict[str, list[str]] = {}
    interim_list = list(interim.values())
    for sid, target in interim.items():
        scored = top_related(target, interim_list, k=5)
        related_by_id[sid] = [c.id for c, _, _ in scored]

    # Final pass: write per-dataset files + assemble manifest.
    written_meta = 0
    written_agent = 0
    final_entries: list[ManifestEntry] = []
    for sid, meta in metas.items():
        agent = agents[sid]
        emb = embeddings[sid]

        _write_dataset_meta(out_root, meta)
        written_meta += 1

        if agent is not None:
            _write_agent_data(out_root, sid, agent)
            written_agent += 1

        entry = _merged_entry(meta, agent, emb)
        entry.related_ids = related_by_id.get(sid, [])
        final_entries.append(entry)

    final_entries.sort(
        key=lambda e: (e.metadata_modified or datetime.min.replace(tzinfo=timezone.utc)),
        reverse=True,
    )
    manifest = Manifest(
        generated_at=datetime.now(timezone.utc),
        datasets=final_entries,
        tag_slugs=_build_tag_slugs(final_entries),
    )
    manifest_path = _write_manifest(out_root, manifest)
    log.info(
        "publish: wrote manifest=%s data.json=%d agent_data.json=%d",
        manifest_path, written_meta, written_agent,
    )
    return {
        "manifest_path": str(manifest_path),
        "datasets": len(final_entries),
        "wrote_data_json": written_meta,
        "wrote_agent_data_json": written_agent,
    }


# ---- CLI --------------------------------------------------------------------

def _cli() -> None:
    p = argparse.ArgumentParser(description="Emit per-dataset + manifest artifacts from Firestore.")
    p.add_argument(
        "--from-firestore",
        action="store_true",
        help="Source from the Firestore `sources` collection (the only mode supported).",
    )
    p.add_argument(
        "--out",
        required=True,
        help="Output root (e.g. frontend/public). Writes data/manifest.json and datasets/<id>/{data,agent_data}.json.",
    )
    args = p.parse_args()

    if not args.from_firestore:
        p.error("only --from-firestore is supported")

    summary = publish(Path(args.out))
    import json
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _cli()
