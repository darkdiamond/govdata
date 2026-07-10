"""Production session runner — one dataset, end-to-end, self-validating.

Replaces the Anthropic Managed Agents `session_runner`. Flow per dataset:

    1. Host-side CKAN schema prefetch (saves the agent its discovery calls).
    2. Up to SESSION_ATTEMPTS (default 3) attempts, each on a fresh
       LocalSandbox workdir:
         a. run the PydanticAI agent session (model_harness.run_agent_session,
            OpenRouter model from OPENROUTER_MODEL)
         b. validate: both files exist → AgentData schema → sanitizer →
            host-side agent/skills/check.py exit 0 on the SANITIZED body.
       A failed attempt (known MiniMax API flakes, missing outputs, or
       validation) logs and retries; only after all attempts fail does the
       dataset count as failed for this run.
    3. On success only: upload content.html to GCS staging and persist
       agent_data + usage/cost telemetry to the Firestore source doc.

The pipeline marks analysis_status around this call; a raised exception
here → mark_analysis_failed (which increments failed_attempts so the
selector can retry on subsequent days, max 3).
"""
from __future__ import annotations

import logging
import os
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from services.shared.firestore import FirestoreStateStore

from .agent_contract import (
    fetch_resource_preview,
    run_host_check,
    sanitize_content_html,
)
from .local_sandbox import LocalSandbox
from .model_harness import (
    AGENT_DATA_FILENAME,
    CONTENT_FILENAME,
    AgentSessionOutput,
    run_agent_session,
)
from .schema import AgentData

log = logging.getLogger(__name__)

DEFAULT_MODEL = "minimax/minimax-m3"
SESSIONS_ROOT = Path(os.environ.get("SESSIONS_ROOT", "/tmp/sessions"))


@dataclass
class ProdSessionResult:
    dataset_id: str
    model: str
    session_id: str
    attempts: int
    elapsed_seconds: float
    usage: dict[str, int]
    cost: dict
    written: list[str] = field(default_factory=list)

    # Back-compat accessors for pipeline summary fields.
    @property
    def events_seen(self) -> int:
        return 0


def _write_gcs(data: bytes, bucket: str, relpath: str) -> str:
    from google.cloud import storage

    client = storage.Client()
    blob = client.bucket(bucket).blob(relpath)
    blob.upload_from_string(data, content_type="text/html; charset=utf-8")
    return f"gs://{bucket}/{relpath}"


def run_production_session(
    *,
    dataset_id: str,
    title: str,
    notes: str,
    org_title: str,
    primary_resource_id: Optional[str] = None,
    gcs_bucket: str,
    store: Optional[FirestoreStateStore] = None,
    model: Optional[str] = None,
) -> ProdSessionResult:
    if not gcs_bucket:
        raise ValueError("gcs_bucket is required")
    model = model or os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL)
    attempts_max = int(os.environ.get("SESSION_ATTEMPTS", "3"))
    store = store or FirestoreStateStore()
    session_id = f"or-{uuid.uuid4().hex[:12]}"
    started = time.monotonic()

    pre_fetched_schema = (
        fetch_resource_preview(primary_resource_id) if primary_resource_id else None
    )
    if pre_fetched_schema is not None:
        log.info(
            "session[%s]: prefetched schema (%d fields, total=%d)",
            dataset_id[:8],
            len(pre_fetched_schema["fields"]),
            pre_fetched_schema["total"],
        )

    SESSIONS_ROOT.mkdir(parents=True, exist_ok=True)
    last_err: Optional[BaseException] = None
    out: Optional[AgentSessionOutput] = None
    content_html: Optional[str] = None
    agent_data: Optional[AgentData] = None
    attempts = 0

    # Spend across ALL attempts, including ones that returned output but
    # failed validation — the closest match to the OpenRouter dashboard.
    # Attempts that die mid-run (API error) never return usage, so their
    # spend stays invisible here; the dashboard remains the authority.
    attempts_cost = 0.0

    for attempt in range(1, attempts_max + 1):
        attempts = attempt
        workdir = Path(
            tempfile.mkdtemp(prefix=f"{dataset_id[:8]}-a{attempt}-", dir=SESSIONS_ROOT)
        )
        sandbox = LocalSandbox.create(workdir)
        try:
            out = run_agent_session(
                sandbox=sandbox,
                model=model,
                dataset_id=dataset_id,
                title=title,
                notes=notes,
                org_title=org_title,
                primary_resource_id=primary_resource_id,
                outputs_dir=str(workdir / "outputs"),
                check_script=str(workdir / "check.py"),
                pre_fetched_schema=pre_fetched_schema,
            )
            attempts_cost += out.cost.get("total_usd") or 0.0
            agent_data = AgentData.model_validate_json(out.agent_data_raw)
            content_html = sanitize_content_html(
                out.content_html_raw, dataset_id=dataset_id
            )
            run_host_check(
                content_html,
                agent_data.model_dump_json(exclude_none=True),
                workdir,
            )
            log.info(
                "session[%s]: attempt %d/%d validated (iters=%d, $%.4f %s)",
                dataset_id[:8], attempt, attempts_max, out.iterations,
                out.cost.get("total_usd") or 0.0, out.cost.get("cost_source"),
            )
            break
        except Exception as e:
            last_err = e
            log.warning(
                "session[%s]: attempt %d/%d failed: %s",
                dataset_id[:8], attempt, attempts_max, str(e)[:300],
            )
        finally:
            sandbox.kill()
    else:
        raise RuntimeError(
            f"all {attempts_max} attempts failed for {dataset_id}; "
            f"last error: {last_err}"
        ) from last_err

    assert out is not None and content_html is not None and agent_data is not None

    written = [
        _write_gcs(
            content_html.encode("utf-8"),
            gcs_bucket,
            f"datasets/{dataset_id}/{CONTENT_FILENAME}",
        )
    ]
    store.set_agent_data(
        dataset_id, agent_data.model_dump(mode="json", exclude_none=True)
    )

    elapsed = round(time.monotonic() - started, 2)
    try:
        store.set_session_usage(
            dataset_id,
            usage={
                **out.usage,
                "actual_cost_usd": out.cost.get("total_usd"),
                "attempts_cost_usd": round(attempts_cost, 6),
                "cost_source": out.cost.get("cost_source"),
                "cost_breakdown": out.cost.get("breakdown"),
                "model": model,
                "attempts": attempts,
            },
            model_requests=out.iterations,
            elapsed_s=elapsed,
            session_id=session_id,
            agent_version=None,
        )
    except Exception:
        # Telemetry failure must never fail a run.
        log.exception("failed to persist last_usage for %s", dataset_id)

    log.info(
        "session[%s]: done in %.1fs (attempts=%d, tokens=%s, cost=%s)",
        dataset_id[:8], elapsed, attempts, out.usage.get("total_tokens"),
        out.cost.get("total_usd"),
    )
    return ProdSessionResult(
        dataset_id=dataset_id,
        model=model,
        session_id=session_id,
        attempts=attempts,
        elapsed_seconds=elapsed,
        usage=out.usage,
        cost=out.cost,
        written=written,
    )
