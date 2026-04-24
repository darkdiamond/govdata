"""HTTP + CLI entrypoint for the page-builder.

Flow per invocation:
    1. Fetch CKAN `package_show` to get the dataset's title, notes, org, and
       the primary CSV resource_id.
    2. Hand off to `session_runner.run_session()`: creates a Managed Agents
       session, streams until the agent is idle, downloads outputs.
    3. (Optional) Refresh the manifest.json + fire a Cloudflare build hook.

Local CLI:
    python -m services.page_builder.main <dataset_id> [--out DIR]
"""
from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
from typing import Optional

import httpx

from .session_runner import run_session

log = logging.getLogger("page_builder")
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))

CKAN_BASE = "https://data.gov.il/api/3/action"
EXCLUDED_FORMATS = {"PDF", "DOC", "DOCX", "ZIP", "RAR", "7Z", "EXE", "MSI"}


def _fetch_package(dataset_id: str) -> dict:
    with httpx.Client(timeout=30.0) as c:
        r = c.get(f"{CKAN_BASE}/package_show", params={"id": dataset_id})
    r.raise_for_status()
    payload = r.json()
    if not payload.get("success"):
        raise RuntimeError(f"package_show failed: {payload.get('error')}")
    return payload["result"]


def _pick_primary_resource(resources: list[dict]) -> Optional[dict]:
    for r in resources:
        if (r.get("format") or "").upper() == "CSV" and r.get("datastore_active"):
            return r
    for r in resources:
        if r.get("datastore_active"):
            return r
    for r in resources:
        if (r.get("format") or "").upper() not in EXCLUDED_FORMATS:
            return r
    return None


def _fire_build_hook(url: Optional[str]) -> None:
    if not url:
        return
    try:
        with httpx.Client(timeout=10.0) as c:
            c.post(url)
        log.info("Cloudflare build hook fired")
    except Exception as e:
        log.warning("build hook failed: %s", e)


def build(dataset_id: str, *, out_dir: Optional[Path] = None) -> dict:
    """Core entrypoint shared by HTTP and CLI. Returns a summary dict."""
    pkg = _fetch_package(dataset_id)
    primary = _pick_primary_resource(pkg.get("resources", []))

    result = run_session(
        dataset_id=pkg["id"],
        title=pkg.get("title", ""),
        notes=pkg.get("notes", "") or "",
        org_title=(pkg.get("organization") or {}).get("title", "") or "",
        primary_resource_id=primary["id"] if primary else None,
        out_dir=out_dir,
        gcs_bucket=None if out_dir else os.environ.get("GCS_CONTENT_BUCKET"),
    )

    # The build hook + manifest refresh happen here, not inside the session
    # runner, so a failed hook doesn't obscure a successful session.
    _fire_build_hook(os.environ.get("CLOUDFLARE_BUILD_HOOK"))

    return {
        "status": "ok",
        "session_id": result.session_id,
        "written": result.written,
        "elapsed_seconds": result.elapsed_seconds,
        "events": result.events_seen,
        "usage": result.usage,
    }


def http_entry(request):
    """GCP Cloud Functions (Functions Framework) HTTP entrypoint.

    Accepts POST {"dataset_id": "..."} — the scanner's webhook shape.
    """
    try:
        body = request.get_json(silent=True) or {}
    except Exception:
        body = {}
    dataset_id = body.get("dataset_id") or request.args.get("dataset_id")
    if not dataset_id:
        return ({"error": "dataset_id is required"}, 400)
    try:
        summary = build(dataset_id)
        return (summary, 200)
    except Exception as e:
        log.exception("build failed for %s", dataset_id)
        return ({"error": str(e), "dataset_id": dataset_id}, 500)


def _cli() -> None:
    p = argparse.ArgumentParser(description="Build a dataset landing page via Managed Agents.")
    p.add_argument("dataset_id")
    p.add_argument("--out", help="Local output directory (if omitted, uses GCS_CONTENT_BUCKET env)")
    args = p.parse_args()

    out_dir = Path(args.out) if args.out else None
    if not out_dir and not os.environ.get("GCS_CONTENT_BUCKET"):
        p.error("either --out or GCS_CONTENT_BUCKET env var is required")

    summary = build(args.dataset_id, out_dir=out_dir)
    print()
    print("=== session complete ===")
    for k, v in summary.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    _cli()
