"""Aggregate all per-dataset `data.json` files into a single manifest.json
the home page consumes. Can run locally or against a GCS bucket.

Called either:
    - at the end of each session run (incremental — one dataset added)
    - as a batch job:  `python -m services.page_builder.manifest`
"""
from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from pydantic import ValidationError

from .schema import Manifest, ManifestEntry

log = logging.getLogger(__name__)


def _iter_local(root: Path) -> Iterable[tuple[str, bytes]]:
    for p in sorted(root.glob("datasets/*/data.json")):
        yield str(p), p.read_bytes()


def _iter_gcs(bucket: str) -> Iterable[tuple[str, bytes]]:
    from google.cloud import storage

    client = storage.Client()
    b = client.bucket(bucket)
    for blob in b.list_blobs(prefix="datasets/"):
        if blob.name.endswith("/data.json"):
            yield f"gs://{bucket}/{blob.name}", blob.download_as_bytes()


def _parse_one(origin: str, body: bytes) -> Optional[ManifestEntry]:
    try:
        raw = json.loads(body.decode("utf-8"))
        return ManifestEntry.model_validate(raw)
    except (json.JSONDecodeError, ValidationError) as e:
        log.warning("skipping malformed %s: %s", origin, e)
        return None


def build_manifest(*, local_root: Optional[Path] = None,
                   gcs_bucket: Optional[str] = None) -> Manifest:
    if bool(local_root) == bool(gcs_bucket):
        raise ValueError("pass exactly one of local_root / gcs_bucket")
    entries: list[ManifestEntry] = []
    iterator = _iter_local(local_root) if local_root else _iter_gcs(gcs_bucket)
    for origin, body in iterator:
        entry = _parse_one(origin, body)
        if entry is not None:
            entries.append(entry)
    entries.sort(
        key=lambda e: (e.metadata_modified or datetime.min.replace(tzinfo=timezone.utc)),
        reverse=True,
    )
    return Manifest(generated_at=datetime.now(timezone.utc), datasets=entries)


def write_manifest(manifest: Manifest, *, local_path: Optional[Path] = None,
                   gcs_bucket: Optional[str] = None) -> str:
    body = manifest.model_dump_json(exclude_none=True, indent=2).encode("utf-8")
    if local_path is not None:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(body)
        return str(local_path)
    if gcs_bucket is not None:
        from google.cloud import storage

        client = storage.Client()
        blob = client.bucket(gcs_bucket).blob("manifest.json")
        blob.upload_from_string(body, content_type="application/json; charset=utf-8")
        return f"gs://{gcs_bucket}/manifest.json"
    raise ValueError("no target (local_path or gcs_bucket)")


def _cli() -> None:
    p = argparse.ArgumentParser(description="Build manifest.json from per-dataset data.json files.")
    p.add_argument("--local", help="Local root dir containing datasets/<id>/data.json")
    p.add_argument("--bucket", help="GCS bucket containing datasets/<id>/data.json (default $GCS_CONTENT_BUCKET)")
    p.add_argument("--out", help="Write manifest.json here (default: next to source)")
    args = p.parse_args()

    bucket = args.bucket or os.environ.get("GCS_CONTENT_BUCKET")
    if args.local and bucket:
        p.error("pass either --local or --bucket, not both")
    if args.local:
        root = Path(args.local)
        manifest = build_manifest(local_root=root)
        out = Path(args.out) if args.out else root / "manifest.json"
        target = write_manifest(manifest, local_path=out)
    elif bucket:
        manifest = build_manifest(gcs_bucket=bucket)
        if args.out:
            target = write_manifest(manifest, local_path=Path(args.out))
        else:
            target = write_manifest(manifest, gcs_bucket=bucket)
    else:
        p.error("specify --local DIR or --bucket NAME (or set GCS_CONTENT_BUCKET)")
        return

    print(f"wrote {target} with {len(manifest.datasets)} dataset(s)")


if __name__ == "__main__":
    _cli()
