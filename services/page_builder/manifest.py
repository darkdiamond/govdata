"""Build `manifest.json` from Firestore.

The publisher (Cloud Build) calls this at deploy time to regenerate the
manifest consumed by the Nuxt home + category pages:

    python -m services.page_builder.manifest --from-firestore \
        --out frontend/public/data/manifest.json

Each `sources/{id}` document with `analysis_status == "succeeded"` carries
a `manifest_entry` field (written by the builder after a successful session).
We parse those into `ManifestEntry` records, sort by `metadata_modified`
DESC, and serialize.
"""
from __future__ import annotations

import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from pydantic import ValidationError

from services.shared.firestore import FirestoreStateStore

from .schema import Manifest, ManifestEntry

log = logging.getLogger(__name__)


def _iter_firestore_entries(store: FirestoreStateStore) -> Iterable[ManifestEntry]:
    for raw in store.iter_manifest_entries():
        try:
            yield ManifestEntry.model_validate(raw)
        except (ValidationError, TypeError) as e:
            log.warning("skipping malformed manifest_entry: %s", e)


def build_manifest(store: Optional[FirestoreStateStore] = None) -> Manifest:
    store = store or FirestoreStateStore()
    entries = list(_iter_firestore_entries(store))
    entries.sort(
        key=lambda e: (e.metadata_modified or datetime.min.replace(tzinfo=timezone.utc)),
        reverse=True,
    )
    return Manifest(generated_at=datetime.now(timezone.utc), datasets=entries)


def write_manifest(manifest: Manifest, out_path: Path) -> str:
    body = manifest.model_dump_json(exclude_none=True, indent=2).encode("utf-8")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(body)
    return str(out_path)


def _cli() -> None:
    p = argparse.ArgumentParser(description="Build manifest.json from Firestore.")
    p.add_argument(
        "--from-firestore",
        action="store_true",
        help="Source manifest entries from the Firestore `sources` collection",
    )
    p.add_argument(
        "--out",
        required=True,
        help="Output path for manifest.json (e.g. frontend/public/data/manifest.json)",
    )
    args = p.parse_args()

    if not args.from_firestore:
        p.error("only --from-firestore is supported in this build")
    manifest = build_manifest()
    target = write_manifest(manifest, Path(args.out))
    print(f"wrote {target} with {len(manifest.datasets)} dataset(s)")


if __name__ == "__main__":
    _cli()
