"""HTTP entrypoint for the govdata-builder Cloud Run service.

One POST from Cloud Scheduler per tick. Drives the pipeline end-to-end via
`pipeline.run_pipeline` and returns a JSON summary.

Request body:
    {}                           → scheduled run (scan + select N)
    {"dataset_id": "<id>"}       → manual override (skip scan, build one)
    {"dry_run": true}            → scan + select only, no agent run
    {"skip_publish": true}       → run agent + write to Firestore/GCS, but
                                   don't fire the Cloud Build publisher
"""
from __future__ import annotations

import asyncio
import json
import logging
import os

from .pipeline import run_pipeline

log = logging.getLogger("page_builder")
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))


def http_entry(request):
    """functions-framework HTTP entrypoint."""
    try:
        body = request.get_json(silent=True) or {}
    except Exception:
        body = {}

    mode = body.get("mode") or ("manual" if body.get("dataset_id") else "scheduled")
    override_id = body.get("dataset_id") or request.args.get("dataset_id")
    dry_run = bool(body.get("dry_run"))
    skip_publish = bool(body.get("skip_publish"))

    try:
        summary = asyncio.run(
            run_pipeline(
                mode=mode,
                override_id=override_id,
                dry_run=dry_run,
                skip_publish=skip_publish,
            )
        )
        return (json.dumps(summary, default=str), 200, {"Content-Type": "application/json"})
    except Exception as e:
        log.exception("pipeline failed")
        return (
            json.dumps({"error": str(e), "mode": mode, "override_id": override_id}, default=str),
            500,
            {"Content-Type": "application/json"},
        )
