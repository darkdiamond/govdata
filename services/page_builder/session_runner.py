"""Managed Agents controller — one session per dataset, stage to GCS.

Flow:
    1. Create session (agent + env).
    2. Stream events until terminal idle or `session.status_terminated`.
       No client-side time cap — the agent decides when it's done.
    3. Download the session's outputs (expect `content.html` + `data.json`).
    4. Parse data.json → ManifestEntry; enrich with a Voyage embedding.
    5. Load existing ManifestEntry records from Firestore and compute the
       top-5 related datasets — persist the result into `entry.related_ids`
       so the Nuxt dataset page can render the sidebar at generate time.
    6. Upload `content.html` (the agent's body) + `data.json` (enriched) to
       `gs://<staging>/datasets/<id>/`. The full page is assembled later by
       `frontend/pages/datasets/[id].vue` during `nuxt generate`.

The manifest is NOT rebuilt here — that's the publisher's job (it reads
Firestore and writes `frontend/public/data/manifest.json` during the
Cloud Build run).
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

from anthropic import Anthropic

from services.shared.firestore import FirestoreStateStore

from .embeddings import embed, embedding_input
from .related import top_related
from .schema import ManifestEntry

log = logging.getLogger(__name__)

MA_BETA = "managed-agents-2026-04-01"
FILES_BETA = "files-api-2025-04-14"

CONTENT_FILENAME = "content.html"
DATA_FILENAME = "data.json"


@dataclass
class SessionResult:
    session_id: str
    title: str
    entry: Optional[ManifestEntry] = None
    written: list[str] = field(default_factory=list)
    events_seen: int = 0
    usage: dict[str, int] = field(default_factory=dict)
    elapsed_seconds: float = 0.0

    def note(self, msg: str) -> None:
        log.info("session[%s]: %s", self.session_id[:10], msg)


def _build_user_message(
    *,
    dataset_id: str,
    title: str,
    notes: str,
    org_title: str,
    primary_resource_id: Optional[str],
) -> str:
    resource_line = (
        f"primary_resource_id: {primary_resource_id}"
        if primary_resource_id
        else "primary_resource_id: (not pre-identified — pick one from package_show)"
    )
    return (
        "Build the landing page for this CKAN dataset. Write content.html "
        "(body fragment only — no <html>/<head>/<body>) and data.json to "
        "/mnt/session/outputs/, following the system prompt and the "
        "govdata-design skill. All user-visible text in content.html must "
        "be Hebrew; your reasoning and bash commands can (and should) stay "
        "in English.\n\n"
        f"dataset_id: {dataset_id}\n"
        f"title (he): {title}\n"
        f"organization (he): {org_title or '(unknown)'}\n"
        f"description (he): {(notes or '(none)')[:1500]}\n"
        f"{resource_line}\n\n"
        "Begin by investigating the dataset. When both files are written, stop."
    )


def _is_terminal(event) -> bool:
    et = getattr(event, "type", None)
    if et == "session.status_terminated":
        return True
    if et == "session.status_idle":
        stop = getattr(event, "stop_reason", None)
        return getattr(stop, "type", None) != "requires_action"
    return False


def _accumulate_usage(event, out: dict[str, int]) -> None:
    if getattr(event, "type", None) != "span.model_request_end":
        return
    mu = getattr(event, "model_usage", None) or {}
    for k in (
        "input_tokens",
        "output_tokens",
        "cache_creation_input_tokens",
        "cache_read_input_tokens",
    ):
        v = mu.get(k) if isinstance(mu, dict) else getattr(mu, k, None)
        out[k] = out.get(k, 0) + int(v or 0)


def _content_type(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".html"):
        return "text/html; charset=utf-8"
    if lower.endswith(".json"):
        return "application/json; charset=utf-8"
    if lower.endswith(".js"):
        return "application/javascript; charset=utf-8"
    if lower.endswith(".css"):
        return "text/css; charset=utf-8"
    return "application/octet-stream"


def _write_gcs(data: bytes, bucket: str, relpath: str) -> str:
    from google.cloud import storage

    client = storage.Client()
    blob = client.bucket(bucket).blob(relpath)
    blob.upload_from_string(data, content_type=_content_type(relpath))
    return f"gs://{bucket}/{relpath}"


def _load_existing_manifest_entries(store: FirestoreStateStore) -> list[ManifestEntry]:
    """Load enriched ManifestEntry records from Firestore for related-scoring."""
    entries: list[ManifestEntry] = []
    try:
        for raw in store.iter_manifest_entries():
            try:
                entries.append(ManifestEntry.model_validate(raw))
            except Exception as e:
                log.warning("skipping malformed manifest_entry: %s", e)
    except Exception as e:
        log.warning("couldn't list succeeded sources: %s", e)
    return entries


def run_session(
    *,
    dataset_id: str,
    title: str,
    notes: str,
    org_title: str,
    primary_resource_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    environment_id: Optional[str] = None,
    api_key: Optional[str] = None,
    gcs_bucket: str,
    store: Optional[FirestoreStateStore] = None,
) -> SessionResult:
    """Run one Managed Agents session end-to-end and upload body-only artifacts to GCS staging."""
    if not gcs_bucket:
        raise ValueError("gcs_bucket is required")

    agent_id = agent_id or os.environ.get("ANTHROPIC_AGENT_ID")
    environment_id = environment_id or os.environ.get("ANTHROPIC_ENV_ID")
    if not agent_id or not environment_id:
        raise RuntimeError(
            "ANTHROPIC_AGENT_ID and ANTHROPIC_ENV_ID are required "
            "(run infra/setup-agent.sh once to create them)"
        )

    client = Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
    store = store or FirestoreStateStore()
    started = time.monotonic()

    session_title = f"build {dataset_id[:8]} — {title[:60]}"
    session = client.beta.sessions.create(
        agent=agent_id, environment_id=environment_id, title=session_title,
    )
    result = SessionResult(session_id=session.id, title=session_title)
    result.note("created")

    user_msg = _build_user_message(
        dataset_id=dataset_id,
        title=title,
        notes=notes,
        org_title=org_title,
        primary_resource_id=primary_resource_id,
    )

    # Stream-first, then send.
    with client.beta.sessions.events.stream(session_id=session.id) as stream:
        client.beta.sessions.events.send(
            session_id=session.id,
            events=[
                {
                    "type": "user.message",
                    "content": [{"type": "text", "text": user_msg}],
                }
            ],
        )
        for event in stream:
            result.events_seen += 1
            _accumulate_usage(event, result.usage)
            if _is_terminal(event):
                result.note(f"terminal event {getattr(event, 'type', '?')}")
                break

    # Collect session outputs. Retry briefly for indexing lag.
    files_list = []
    for _ in range(3):
        page = client.beta.files.list(
            scope_id=session.id, betas=[MA_BETA, FILES_BETA]
        )
        files_list = list(page)
        if files_list:
            break
        time.sleep(1)
    if not files_list:
        raise RuntimeError(f"session {session.id} produced no outputs")

    result.note(f"{len(files_list)} output file(s)")

    content_html: Optional[str] = None
    data_json_bytes: Optional[bytes] = None
    extras: list[tuple[str, bytes]] = []
    for f in files_list:
        fname = (f.filename or f.id).lstrip("/")
        if ".." in fname.split("/"):
            log.warning("refusing unsafe filename: %s", fname)
            continue
        body = client.beta.files.download(f.id).read()
        if fname == CONTENT_FILENAME or fname.endswith("/" + CONTENT_FILENAME):
            content_html = body.decode("utf-8", errors="replace")
        elif fname == DATA_FILENAME or fname.endswith("/" + DATA_FILENAME):
            data_json_bytes = body
        else:
            extras.append((fname, body))

    if content_html is None or data_json_bytes is None:
        raise RuntimeError(
            f"session {session.id} missing required outputs: "
            f"content.html={content_html is not None}, "
            f"data.json={data_json_bytes is not None}"
        )

    entry = ManifestEntry.model_validate_json(data_json_bytes)
    if entry.embedding is None:
        text = embedding_input(
            entry.title, entry.summary_he, entry.organization, entry.tags_he
        )
        entry.embedding = embed(text)

    # Compute related from Firestore-known succeeded sources and persist the
    # top-5 onto the entry. The agent's own related_ids suggestion gets
    # folded in via AGENT_SUGGESTED_WEIGHT inside top_related().
    candidates = _load_existing_manifest_entries(store)
    candidates = [e for e in candidates if e.id != entry.id]
    related_scored = top_related(entry, candidates, k=5)
    entry.related_ids = [c.id for c, _, _ in related_scored]
    result.note(f"related: {[rid[:8] for rid in entry.related_ids]}")

    prefix = f"datasets/{entry.id}"
    enriched_json = entry.model_dump_json(exclude_none=True, indent=2).encode("utf-8")
    writes: list[tuple[str, bytes]] = [
        (f"{prefix}/{DATA_FILENAME}", enriched_json),
        (f"{prefix}/{CONTENT_FILENAME}", content_html.encode("utf-8")),
    ]
    for name, body in extras:
        writes.append((f"{prefix}/{name}", body))

    for relpath, body in writes:
        result.written.append(_write_gcs(body, gcs_bucket, relpath))

    result.entry = entry
    result.elapsed_seconds = round(time.monotonic() - started, 2)
    result.note(
        f"done in {result.elapsed_seconds}s "
        f"(events={result.events_seen}, usage={result.usage})"
    )
    return result
