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

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import urlencode

from anthropic import Anthropic

from services.shared.firestore import FirestoreStateStore

from .schema import AgentData

log = logging.getLogger(__name__)

MA_BETA = "managed-agents-2026-04-01"
FILES_BETA = "files-api-2025-04-14"

CONTENT_FILENAME = "content.html"
AGENT_DATA_FILENAME = "agent_data.json"

# CKAN schema prefetch — skip the agent's first 5–10 schema-discovery curls
# by inlining `fields + total + sample_rows` into the user message. The WAF
# 403s requests without a browser User-Agent (see scanner notes), and the
# CKAN response can be ~50 MB without `limit`, so we hardcode limit=5 and a
# tight wall-clock budget. On any error we return None and the agent falls
# back to its existing curl flow — never block the build on prefetch.
_CKAN_DATASTORE_URL = "https://data.gov.il/api/3/action/datastore_search"
_CKAN_BROWSER_UA = "Mozilla/5.0 (compatible; govdata-builder/1.0)"
_PREFETCH_TIMEOUT_S = 4.0
_PREFETCH_SAMPLE_LIMIT = 5
_PREFETCH_VALUE_TRUNC = 80
_PREFETCH_JSON_CAP = 2048


def _truncate_value(v: Any) -> Any:
    if isinstance(v, str) and len(v) > _PREFETCH_VALUE_TRUNC:
        return v[: _PREFETCH_VALUE_TRUNC - 1] + "…"
    return v


def _fetch_resource_preview(resource_id: str) -> Optional[dict]:
    """Fetch fields + total + 5 sample rows for a CKAN resource.

    Returns ``{"fields": [{id,type}], "total": int, "sample_rows": [...]}``
    on success; ``None`` on any error (timeout, HTTP 4xx/5xx, JSON parse
    failure, missing keys). The agent's prompt accepts the absence
    silently and falls back to its current schema-discovery flow.
    """
    if not resource_id:
        return None
    qs = urlencode(
        {
            "resource_id": resource_id,
            "limit": _PREFETCH_SAMPLE_LIMIT,
            "include_total": "true",
        }
    )
    url = f"{_CKAN_DATASTORE_URL}?{qs}"
    req = urllib_request.Request(url, headers={"User-Agent": _CKAN_BROWSER_UA})
    last_err: Optional[BaseException] = None
    for attempt in (1, 2):
        try:
            with urllib_request.urlopen(req, timeout=_PREFETCH_TIMEOUT_S) as resp:
                payload = json.loads(resp.read().decode("utf-8", errors="replace"))
            break
        except (urllib_error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last_err = e
            if attempt == 1:
                continue
    else:
        log.warning(
            "ckan prefetch %s failed after retry: %s", resource_id[:8], last_err
        )
        return None
    if not payload.get("success"):
        log.warning("ckan prefetch %s success=false", resource_id[:8])
        return None
    result = payload.get("result") or {}
    fields = [
        {"id": f.get("id"), "type": f.get("type")}
        for f in (result.get("fields") or [])
        if f.get("id")
    ]
    rows = []
    for row in (result.get("records") or [])[: _PREFETCH_SAMPLE_LIMIT]:
        rows.append({k: _truncate_value(v) for k, v in row.items() if k != "_id"})
    preview = {
        "fields": fields,
        "total": int(result.get("total") or 0),
        "sample_rows": rows,
    }
    # Hard cap the serialized size so a wide table doesn't bloat the prompt.
    serialized = json.dumps(preview, ensure_ascii=False, separators=(",", ":"))
    if len(serialized.encode("utf-8")) > _PREFETCH_JSON_CAP:
        # Drop sample rows progressively until we fit; keep fields + total.
        while preview["sample_rows"] and len(
            json.dumps(preview, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ) > _PREFETCH_JSON_CAP:
            preview["sample_rows"].pop()
    return preview

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
_SCRIPT_BLOCK = re.compile(
    r"(<script\b[^>]*>)(.*?)(</script\s*>)", re.IGNORECASE | re.DOTALL
)
_SCRIPT_DATA_TYPE = re.compile(
    r'\btype\s*=\s*"(?:application/(?:[a-z0-9-]+\+)?json|text/[a-z0-9-]+)"',
    re.IGNORECASE,
)
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


_JS_CTRL_ESCAPES: dict[str, str] = {
    "\x08": "\\b",
    "\x09": "\\t",
    "\x0a": "\\n",
    "\x0b": "\\v",
    "\x0c": "\\f",
    "\x0d": "\\r",
    "\u2028": "\\u2028",
    "\u2029": "\\u2029",
}
for _i in list(range(0x00, 0x08)) + [0x0e, 0x0f] + list(range(0x10, 0x20)):
    _JS_CTRL_ESCAPES.setdefault(chr(_i), f"\\u{_i:04x}")


def _escape_js_string_controls(script_body: str) -> tuple[str, int]:
    # Walk the script body tracking comment/string state and replace any raw
    # control char or line terminator inside `"…"` / `'…'` literals with its
    # JS escape. CKAN address fields routinely carry embedded LFs; when the
    # agent inlines a row array as a JS literal those LFs land *unescaped*
    # inside the string and V8 aborts the whole <script> with "Invalid or
    # unexpected token" — taking every chart and the Leaflet map down with
    # it (b2370286-… exhibited exactly this).
    out: list[str] = []
    i = 0
    n = len(script_body)
    count = 0
    while i < n:
        c = script_body[i]
        # Line comment — preserve verbatim.
        if c == "/" and i + 1 < n and script_body[i + 1] == "/":
            j = script_body.find("\n", i)
            if j < 0:
                j = n
            out.append(script_body[i:j])
            i = j
            continue
        # Block comment — preserve verbatim.
        if c == "/" and i + 1 < n and script_body[i + 1] == "*":
            j = script_body.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append(script_body[i:j])
            i = j
            continue
        # Template literal — raw newlines are legal here, leave as-is. We do
        # not try to parse `${…}` interpolation; for the purpose of this
        # sanitizer it's enough to skip to the matching backtick honouring
        # backslash escape.
        if c == "`":
            out.append(c)
            i += 1
            while i < n:
                ch = script_body[i]
                if ch == "\\" and i + 1 < n:
                    out.append(script_body[i:i + 2])
                    i += 2
                    continue
                out.append(ch)
                i += 1
                if ch == "`":
                    break
            continue
        # `'…'` / `"…"` string — the only place we actually escape.
        if c == '"' or c == "'":
            quote = c
            out.append(quote)
            i += 1
            while i < n:
                ch = script_body[i]
                if ch == "\\" and i + 1 < n:
                    out.append(script_body[i:i + 2])
                    i += 2
                    continue
                if ch == quote:
                    out.append(quote)
                    i += 1
                    break
                esc = _JS_CTRL_ESCAPES.get(ch)
                if esc is not None:
                    out.append(esc)
                    count += 1
                    i += 1
                    continue
                out.append(ch)
                i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out), count


def _escape_script_string_controls(body: str, *, tag: str) -> str:
    total = 0

    def handle(match: "re.Match[str]") -> str:
        nonlocal total
        opener, inner, closer = match.group(1), match.group(2), match.group(3)
        # Skip data blocks (JSON-LD, application/json, etc.) — those aren't
        # parsed as JS, raw newlines are fine and "fixing" them would break
        # the JSON.
        if _SCRIPT_DATA_TYPE.search(opener):
            return match.group(0)
        new_inner, n = _escape_js_string_controls(inner)
        total += n
        return opener + new_inner + closer

    new_body = _SCRIPT_BLOCK.sub(handle, body)
    if total:
        log.warning(
            "%ssanitizer: escaped %d raw control char(s) in JS string literal(s)",
            tag, total,
        )
    return new_body


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
    Escapes raw control chars (LF/CR/etc.) inside `"…"`/`'…'` JS string
    literals (b2370286-… inlined CKAN address fields containing embedded
    newlines as a JS array literal — V8 aborted the whole <script> on the
    first one, blanking 4 ECharts + the Leaflet map).

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

    # Run after balancing so every <script> has a closer the regex can find.
    body = _escape_script_string_controls(body, tag=tag)

    return body


@dataclass
class SessionResult:
    session_id: str
    title: str
    dataset_id: str = ""
    agent_data: Optional[AgentData] = None
    written: list[str] = field(default_factory=list)
    events_seen: int = 0
    # Number of `span.model_request_end` events — i.e. how many times the
    # API re-evaluated the cached prefix. Each one accrues cache_read tokens.
    model_requests: int = 0
    usage: dict[str, int] = field(default_factory=dict)
    elapsed_seconds: float = 0.0

    def note(self, msg: str) -> None:
        log.info("session[%s]: %s", self.session_id[:10], msg)


def build_user_message(
    *,
    dataset_id: str,
    title: str,
    notes: str,
    org_title: str,
    primary_resource_id: Optional[str],
    pre_fetched_schema: Optional[dict] = None,
    outputs_dir: str = "/mnt/session/outputs/",
) -> str:
    resource_line = (
        f"primary_resource_id: {primary_resource_id}"
        if primary_resource_id
        else "primary_resource_id: (not pre-identified — pick one from package_show)"
    )
    od = outputs_dir.rstrip("/") + "/"
    schema_block = ""
    if pre_fetched_schema:
        schema_json = json.dumps(
            pre_fetched_schema, ensure_ascii=False, separators=(",", ":")
        )
        schema_block = (
            "\n\npre_fetched_schema (already retrieved host-side from "
            "datastore_search; SKIP package_show + the schema-discovery "
            "datastore_search call — go straight to aggregations):\n"
            f"```json\n{schema_json}\n```"
        )
    return (
        "Build the landing page for this CKAN dataset. Write content.html "
        "(body fragment only — no <html>/<head>/<body>) and agent_data.json "
        f"to {od}, following the system prompt. All "
        "user-visible text in content.html must be Hebrew; your reasoning "
        "and bash commands can (and should) stay in English.\n\n"
        f"dataset_id: {dataset_id}\n"
        f"title (he): {title}\n"
        f"organization (he): {org_title or '(unknown)'}\n"
        f"description (he): {(notes or '(none)')[:1500]}\n"
        f"{resource_line}"
        f"{schema_block}\n\n"
        "Begin by investigating the dataset. When both files are written, stop."
    )


_build_user_message = build_user_message


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
    create_kwargs: dict[str, Any] = {
        "agent": agent_id,
        "environment_id": environment_id,
        "title": session_title,
    }
    # Mount the self-check script. The Managed Agents runtime prefixes
    # `mount_path` with `/mnt/session/uploads/`, so requesting
    # `/check.py` here lands the file at `/mnt/session/uploads/check.py`
    # inside the container — that's the path the agent yaml invokes.
    # (Asking for `/workspace/check.py` placed it at
    # `/mnt/session/uploads/workspace/check.py`, which surprised the
    # agent's `python3 /workspace/check.py …` invocation.)
    # Upload via `infra/upload-check-script.py` and export the resulting
    # file_id as ANTHROPIC_CHECK_PY_FILE_ID; if unset, no resource is
    # attached and the agent will hit a "No such file" on the self-check
    # bash call. Set the env var for prod.
    check_py_file_id = os.environ.get("ANTHROPIC_CHECK_PY_FILE_ID")
    if check_py_file_id:
        create_kwargs["resources"] = [
            {
                "type": "file",
                "file_id": check_py_file_id,
                "mount_path": "/check.py",
            }
        ]
    session = client.beta.sessions.create(**create_kwargs)
    result = SessionResult(session_id=session.id, title=session_title, dataset_id=dataset_id)
    result.note("created")

    pre_fetched_schema = (
        _fetch_resource_preview(primary_resource_id) if primary_resource_id else None
    )
    if pre_fetched_schema is not None:
        result.note(
            f"prefetched schema: {len(pre_fetched_schema['fields'])} fields, "
            f"total={pre_fetched_schema['total']}, "
            f"sample={len(pre_fetched_schema['sample_rows'])}"
        )

    user_msg = _build_user_message(
        dataset_id=dataset_id,
        title=title,
        notes=notes,
        org_title=org_title,
        primary_resource_id=primary_resource_id,
        pre_fetched_schema=pre_fetched_schema,
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
            if getattr(event, "type", None) == "span.model_request_end":
                result.model_requests += 1
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

    # Files we mount as session resources (e.g. /workspace/check.py)
    # show up in `files.list(scope_id=session.id)` but error on download
    # as "not downloadable" — they're inputs, not outputs. Skip by
    # basename. If we ever mount anything else read-only into the
    # session container, add it here.
    SESSION_INPUT_BASENAMES = {"check.py"}

    content_html: Optional[str] = None
    agent_data_bytes: Optional[bytes] = None
    extras: list[tuple[str, bytes]] = []
    for f in files_list:
        fname = (f.filename or f.id).lstrip("/")
        if ".." in fname.split("/"):
            log.warning("refusing unsafe filename: %s", fname)
            continue
        basename = fname.rsplit("/", 1)[-1]
        if basename in SESSION_INPUT_BASENAMES:
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

    # Persist token usage for cost A/B tracking. Overwrites prior run's
    # numbers — keep history out of the source doc and rely on logs +
    # session_id back-reference if you need a longer trail.
    agent_version_env = os.environ.get("ANTHROPIC_AGENT_VERSION")
    agent_version: Optional[int] = None
    if agent_version_env:
        try:
            agent_version = int(agent_version_env)
        except ValueError:
            log.warning("ANTHROPIC_AGENT_VERSION=%r not int; skipping", agent_version_env)
    try:
        store.set_session_usage(
            dataset_id,
            usage=result.usage,
            model_requests=result.model_requests,
            elapsed_s=result.elapsed_seconds,
            session_id=session.id,
            agent_version=agent_version,
        )
    except Exception:
        # Telemetry failure must never fail a run.
        log.exception("failed to persist last_usage for %s", dataset_id)

    result.note(
        f"done in {result.elapsed_seconds}s "
        f"(events={result.events_seen}, model_requests={result.model_requests}, "
        f"usage={result.usage})"
    )
    return result
