"""Managed Agents controller — one session per dataset, stage to GCS.

Flow:
    1. Create session (agent + env).
    2. Stream events until terminal idle or `session.status_terminated`.
       No client-side time cap — the agent decides when it's done.
    3. Download the session's outputs (expect `content.html` + `agent_data.json`).
    4. Validate agent_data.json against the AgentData schema and persist it
       under `sources/<id>.agent_data` in Firestore.
    5. Upload `content.html` to `gs://<staging>/datasets/<id>/`. (Scanner
       facts and the agent_data field are already on the Firestore source
       doc; the publisher writes per-dataset `data.json` + `agent_data.json`
       from there at deploy time.)

The publisher (`services.page_builder.publish`) owns embedding, related-
dataset scoring, and all per-dataset JSON file emission — kept in one
place so manifest.json and per-dataset files always agree.
"""
from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Optional

from anthropic import Anthropic

from services.shared.firestore import FirestoreStateStore

from .schema import AgentData

log = logging.getLogger(__name__)

MA_BETA = "managed-agents-2026-04-01"
FILES_BETA = "files-api-2025-04-14"

CONTENT_FILENAME = "content.html"
AGENT_DATA_FILENAME = "agent_data.json"

# Belt-and-braces cleanup for agent-emitted body fragments. The agent
# prompt forbids `<script src=>` / `<link>` / `integrity=` / `<\/script>`,
# but LLM hallucinations recur (one dataset shipped with both a fabricated
# SRI hash on Leaflet AND `<\/script>` JSON-escape in every script-end tag,
# silently breaking all viz). These regexes catch the same classes of bug
# at the staging boundary so a regression on the prompt side never reaches
# production. Each rule logs a WARNING when it fires.
_SCRIPT_END_ESCAPED = re.compile(r"<\\/script(\s*)>", re.IGNORECASE)
_INTEGRITY_ATTR = re.compile(r'\s+integrity\s*=\s*"[^"]*"', re.IGNORECASE)
_CROSSORIGIN_ATTR = re.compile(r'\s+crossorigin(?:\s*=\s*"[^"]*")?', re.IGNORECASE)
_CDN_HOSTS = r"(?:[\w-]+\.)*(?:unpkg\.com|cdn\.jsdelivr\.net|cdnjs\.cloudflare\.com)"
_SCRIPT_CDN_TAG = re.compile(
    rf'<script\b[^>]*\bsrc\s*=\s*"https?://{_CDN_HOSTS}[^"]*"[^>]*>\s*(?:</script>)?',
    re.IGNORECASE,
)
_LINK_CDN_TAG = re.compile(
    rf'<link\b[^>]*\bhref\s*=\s*"https?://{_CDN_HOSTS}[^"]*"[^>]*/?>',
    re.IGNORECASE,
)
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_OPEN_SCRIPT = re.compile(r"<script\b[^>]*>", re.IGNORECASE)
_CLOSE_SCRIPT = re.compile(r"</script\s*>", re.IGNORECASE)
_OPEN_STYLE = re.compile(r"<style\b[^>]*>", re.IGNORECASE)
_CLOSE_STYLE = re.compile(r"</style\s*>", re.IGNORECASE)
# Above this many missing closers the body is structurally broken in
# ways a string-append can't safely fix — fail loudly instead.
_MAX_AUTO_REPAIR = 5


def _balance_raw_text_tag(
    body: str,
    opener: re.Pattern,
    closer: re.Pattern,
    name: str,
    *,
    tag: str,
) -> str:
    # `<script>` and `<style>` put the parser in a raw-text state until
    # the matching `</…>`; an unclosed opener swallows the rest of the
    # document, breaks the inline JS, and (for the agent body) blocks
    # Nuxt hydration. Auto-repair: if opens > closes, append the missing
    # closers so the parser can exit raw-text state cleanly.
    counted = _HTML_COMMENT.sub("", body)
    opens = len(opener.findall(counted))
    closes = len(closer.findall(counted))
    delta = opens - closes
    if delta == 0:
        return body
    if delta < 0:
        log.warning(
            "%ssanitizer: %d stray </%s> than <%s> — leaving as-is",
            tag, -delta, name, name,
        )
        return body
    if delta > _MAX_AUTO_REPAIR:
        raise ValueError(
            f"{tag}sanitizer: {delta} unclosed <{name}> tags exceeds "
            f"auto-repair cap ({_MAX_AUTO_REPAIR}); refusing to publish"
        )
    log.warning("%ssanitizer: appended %d missing </%s> tag(s)", tag, delta, name)
    sep = "" if body.endswith("\n") else "\n"
    return body + sep + (f"</{name}>\n" * delta)


def _sanitize_content_html(body: str, *, dataset_id: str = "") -> str:
    """Strip agent-output failure modes that recur as LLM hallucinations.

    Drops `<script src=>` / `<link href=>` to known CDNs (unpkg, jsdelivr,
    cdnjs) — the Nuxt shell pre-loads ECharts/Leaflet/MarkerCluster
    same-origin and the agent contract forbids external resource refs.
    Strips `integrity=` / `crossorigin=` attributes (any SRI hash the
    agent emits is fabricated; same-origin loads don't need either).
    Replaces `<\\/script>` (JSON string-escape) with `</script>` so the
    HTML parser actually closes the tag. Auto-closes unclosed
    `<script>`/`<style>` tags (e4a5e2d7-… shipped without the trailing
    `</script>`, which let the parser swallow the page footer and the
    Nuxt config bootstrap, blanking every chart and breaking hydration).

    Each transform logs a WARNING with a count and the dataset id so we
    can trace prompt regressions even when the sanitizer silently fixes
    them.
    """
    tag = f"[{dataset_id}] " if dataset_id else ""

    new_body, n = _SCRIPT_END_ESCAPED.subn(r"</script\1>", body)
    if n:
        log.warning("%ssanitizer: replaced %d <\\/script> -> </script>", tag, n)
    body = new_body

    new_body, n = _INTEGRITY_ATTR.subn("", body)
    if n:
        log.warning("%ssanitizer: stripped %d integrity= attribute(s)", tag, n)
    body = new_body

    new_body, n = _CROSSORIGIN_ATTR.subn("", body)
    if n:
        log.warning("%ssanitizer: stripped %d crossorigin attribute(s)", tag, n)
    body = new_body

    new_body, n = _SCRIPT_CDN_TAG.subn("", body)
    if n:
        log.warning("%ssanitizer: dropped %d <script src=CDN> tag(s)", tag, n)
    body = new_body

    new_body, n = _LINK_CDN_TAG.subn("", body)
    if n:
        log.warning("%ssanitizer: dropped %d <link href=CDN> tag(s)", tag, n)
    body = new_body

    body = _balance_raw_text_tag(body, _OPEN_SCRIPT, _CLOSE_SCRIPT, "script", tag=tag)
    body = _balance_raw_text_tag(body, _OPEN_STYLE, _CLOSE_STYLE, "style", tag=tag)

    return body


@dataclass
class SessionResult:
    session_id: str
    title: str
    dataset_id: str = ""
    agent_data: Optional[AgentData] = None
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
        "(body fragment only — no <html>/<head>/<body>) and agent_data.json "
        "to /mnt/session/outputs/, following the system prompt and the "
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
    """Run one Managed Agents session end-to-end.

    Side effects on success:
      - `gs://<gcs_bucket>/datasets/<id>/content.html` written (plus any agent extras).
      - `sources/<id>.agent_data` set on the Firestore source doc.
    """
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
    result = SessionResult(session_id=session.id, title=session_title, dataset_id=dataset_id)
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
    agent_data_bytes: Optional[bytes] = None
    extras: list[tuple[str, bytes]] = []
    for f in files_list:
        fname = (f.filename or f.id).lstrip("/")
        if ".." in fname.split("/"):
            log.warning("refusing unsafe filename: %s", fname)
            continue
        body = client.beta.files.download(f.id).read()
        if fname == CONTENT_FILENAME or fname.endswith("/" + CONTENT_FILENAME):
            content_html = body.decode("utf-8", errors="replace")
        elif fname == AGENT_DATA_FILENAME or fname.endswith("/" + AGENT_DATA_FILENAME):
            agent_data_bytes = body
        else:
            extras.append((fname, body))

    if content_html is None or agent_data_bytes is None:
        raise RuntimeError(
            f"session {session.id} missing required outputs: "
            f"content.html={content_html is not None}, "
            f"agent_data.json={agent_data_bytes is not None}"
        )

    agent_data = AgentData.model_validate_json(agent_data_bytes)

    content_html = _sanitize_content_html(content_html, dataset_id=dataset_id)

    prefix = f"datasets/{dataset_id}"
    writes: list[tuple[str, bytes]] = [
        (f"{prefix}/{CONTENT_FILENAME}", content_html.encode("utf-8")),
    ]
    for name, body in extras:
        writes.append((f"{prefix}/{name}", body))

    for relpath, body in writes:
        result.written.append(_write_gcs(body, gcs_bucket, relpath))

    # Persist agent's judgments to Firestore so the publisher can write
    # `agent_data.json` and merge into manifest.json on the next deploy.
    store.set_agent_data(
        dataset_id, agent_data.model_dump(mode="json", exclude_none=True)
    )

    result.agent_data = agent_data
    result.elapsed_seconds = round(time.monotonic() - started, 2)
    result.note(
        f"done in {result.elapsed_seconds}s "
        f"(events={result.events_seen}, usage={result.usage})"
    )
    return result
