"""Builder pipeline — what a single Cloud Run invocation does.

Daily batch (Cloud Scheduler, 07:00 Asia/Jerusalem): scan CKAN → select
every never-analyzed (or retryable-failed) source up to DAILY_CAP →
run all agent sessions concurrently (asyncio.gather bounded by
Semaphore(MAX_CONCURRENT)) → mark each source in Firestore → if ≥1 page
succeeded, trigger the Cloud Build publisher (no new pages → no build).

All parallelism is in-process. Cloud Run is pinned to one container
(`--max-instances=1 --concurrency=1`), so a scheduler tick produces
exactly one pipeline run; sessions are PydanticAI agent loops calling
OpenRouter (OPENROUTER_MODEL), with tool execution in per-session
subprocess sandboxes inside this same container.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from services.scanner.config import ScannerSettings
from services.scanner.main import Scanner
from services.scanner.state import StateDB
from services.shared.firestore import FirestoreStateStore, SourceRecord
from services.shared.resources import pick_primary_resource_id

from . import selector
from .agent_runner import run_production_session

log = logging.getLogger("page_builder.pipeline")


async def _build_one(
    src: SourceRecord,
    staging_bucket: str,
    store: FirestoreStateStore,
    sem: asyncio.Semaphore,
) -> dict:
    """Run one self-validating agent session. Updates Firestore either way."""
    async with sem:
        log.info("building %s — %s", src.id[:8], (src.title or "")[:60])
        # Capture the source's metadata_modified *before* the agent runs — this
        # is the data vintage the agent's content will be based on. Persisted on
        # success so the dataset page can show "המידע נכון ל-X" honestly even
        # after CKAN re-publishes a newer version.
        analyzed_metadata_modified = src.metadata_modified
        await asyncio.to_thread(store.mark_analysis_pending, src.id)

        primary_id = pick_primary_resource_id(src.resources)
        try:
            result = await asyncio.to_thread(
                run_production_session,
                dataset_id=src.id,
                title=src.title,
                notes=src.notes or "",
                org_title=(src.organization or {}).get("title", "") or "",
                primary_resource_id=primary_id,
                gcs_bucket=staging_bucket,
                store=store,
            )
        except Exception as e:
            log.exception("build failed for %s", src.id)
            await asyncio.to_thread(store.mark_analysis_failed, src.id, str(e))
            return {"id": src.id, "status": "failed", "error": str(e)}

        # run_production_session already wrote `sources/<id>.agent_data`.
        page_path = f"datasets/{src.id}/"
        await asyncio.to_thread(
            store.mark_analysis_succeeded,
            src.id,
            page_path,
            analyzed_metadata_modified,
        )
        return {
            "id": src.id,
            "status": "succeeded",
            "session_id": result.session_id,
            "attempts": result.attempts,
            "elapsed_seconds": result.elapsed_seconds,
            "usage": result.usage,
            "cost": result.cost,
            "written": result.written,
        }


async def _trigger_publish(
    project_id: str, trigger_id: str, branch: str, region: str = "me-west1"
) -> Optional[str]:
    """Fire the Cloud Build publisher. Fire-and-forget — don't wait for the build.

    Uses the regional Cloud Build endpoint; triggers created with
    `--region=me-west1` are not reachable via the global endpoint.
    """

    def _run() -> Optional[str]:
        from google.api_core.client_options import ClientOptions
        from google.cloud.devtools import cloudbuild_v1
        from google.cloud.devtools.cloudbuild_v1.types import RunBuildTriggerRequest
        from google.cloud.devtools.cloudbuild_v1.types import RepoSource

        client = cloudbuild_v1.CloudBuildClient(
            client_options=ClientOptions(
                api_endpoint=f"{region}-cloudbuild.googleapis.com"
            )
        )
        request = RunBuildTriggerRequest(
            name=f"projects/{project_id}/locations/{region}/triggers/{trigger_id}",
            project_id=project_id,
            trigger_id=trigger_id,
            source=RepoSource(branch_name=branch),
        )
        operation = client.run_build_trigger(request=request)
        meta = getattr(operation, "metadata", None)
        build = getattr(meta, "build", None)
        return getattr(build, "id", None) if build else None

    try:
        return await asyncio.to_thread(_run)
    except Exception as e:
        log.exception("trigger_publish failed")
        return None


async def run_pipeline(
    *,
    mode: str = "scheduled",
    override_id: Optional[str] = None,
    dry_run: bool = False,
    n_per_run: Optional[int] = None,
    skip_publish: bool = False,
) -> dict:
    """The one entry point the HTTP handler and the CLI both use."""
    store = FirestoreStateStore()
    db = StateDB(store=store)
    config = ScannerSettings()

    # DAILY_CAP bounds "analyze everything new" — purely a cost fuse;
    # anything past the cap stays `never` and is picked up tomorrow.
    n = n_per_run if n_per_run is not None else int(os.environ.get("DAILY_CAP", "50"))
    max_concurrent = int(os.environ.get("MAX_CONCURRENT", "8"))
    # Stopgap knob: pause Track 2 re-analysis (sources CKAN re-flagged as
    # updated) until structural-change gating lands. Track 1 still runs.
    reanalyze = os.environ.get("REANALYZE_ENABLED", "true").lower() not in (
        "false",
        "0",
        "no",
    )
    scan_limit = int(os.environ.get("SCAN_LIMIT", "500"))
    staging_bucket = os.environ.get("GCS_STAGING_BUCKET", "")
    project_id = (
        os.environ.get("FIREBASE_PROJECT")
        or os.environ.get("GOOGLE_CLOUD_PROJECT")
        or "govdata-il"
    )
    trigger_id = os.environ.get("PUBLISH_TRIGGER_ID", "govdata-publish")
    publish_branch = os.environ.get("PUBLISH_BRANCH", "main")
    publish_region = os.environ.get("PUBLISH_REGION", "me-west1")

    if not dry_run and not override_id and not staging_bucket:
        raise RuntimeError(
            "GCS_STAGING_BUCKET must be set for a real pipeline run"
        )

    # [1] scan — unless override_id is set (manual single-source invoke)
    scan_summary = None
    if not override_id:
        scanner = Scanner(config=config, db=db)
        scan_summary = await scanner.scan(limit=scan_limit, mode=mode)

    # [2] select
    if override_id:
        src = await asyncio.to_thread(store.get_source, override_id)
        if src is None:
            raise RuntimeError(f"override source {override_id} not found in Firestore")
        to_process = [src]
    else:
        to_process = await asyncio.to_thread(
            selector.pick_next, store, n, reanalyze=reanalyze
        )

    summary: dict = {
        "mode": mode,
        "dry_run": dry_run,
        "selected": [s.id for s in to_process],
        "scan": _scan_summary_dict(scan_summary) if scan_summary else None,
    }

    if dry_run or not to_process:
        summary["processed"] = []
        summary["build_id"] = None
        summary["status"] = "idle" if not to_process else "dry_run"
        return summary

    # [3] fan-out agent sessions, bounded by MAX_CONCURRENT.
    # `_build_one` runs the sync agent loop via `asyncio.to_thread`, which
    # uses the event loop's default ThreadPoolExecutor. That executor's
    # default cap is `min(32, os.cpu_count() + 4)` — on a 2-CPU Cloud Run
    # container that's ~8, which would silently bottleneck below
    # MAX_CONCURRENT (plus the Firestore mark calls also ride this pool).
    # Widen it; the semaphore is the real concurrency control.
    loop = asyncio.get_running_loop()
    loop.set_default_executor(
        ThreadPoolExecutor(max_workers=max(max_concurrent * 2, 16))
    )
    sem = asyncio.Semaphore(max_concurrent)
    results = await asyncio.gather(
        *[_build_one(src, staging_bucket, store, sem) for src in to_process]
    )
    summary["processed"] = results
    succeeded_ids = [r["id"] for r in results if r.get("status") == "succeeded"]

    # [4] trigger publisher if any page was written
    build_id = None
    if succeeded_ids and trigger_id and not skip_publish:
        build_id = await _trigger_publish(
            project_id, trigger_id, publish_branch, region=publish_region
        )
    summary["build_id"] = build_id
    summary["status"] = "ok" if succeeded_ids else "all_failed"
    return summary


def _scan_summary_dict(s) -> dict:
    return {
        "sources_seen": s.datasets_scanned,
        "new": s.datasets_new,
        "updated": s.datasets_updated,
        "unchanged": s.datasets_unchanged,
        "errors": list(s.errors or []),
    }


def _cli() -> None:
    p = argparse.ArgumentParser(description="Run the builder pipeline locally.")
    p.add_argument("--source", help="Specific dataset_id to build (skip scan+select)")
    p.add_argument("--dry-run", action="store_true", help="Scan + select but don't build")
    p.add_argument("--n", type=int, default=None, help="Override DAILY_CAP")
    p.add_argument("--no-trigger-publish", action="store_true",
                   help="Skip Cloud Build trigger after successful builds")
    args = p.parse_args()

    summary = asyncio.run(
        run_pipeline(
            mode="manual",
            override_id=args.source,
            dry_run=args.dry_run,
            n_per_run=args.n,
            skip_publish=args.no_trigger_publish,
        )
    )
    import json
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    _cli()
