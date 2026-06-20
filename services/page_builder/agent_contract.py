"""The page-builder agent's I/O contract — shared by production and the
local test harness.

Three concerns live here:

1. `build_user_message` — the first (and only) user message an agent
   session receives: dataset facts + the per-session OUTPUTS_DIR and
   CHECK_SCRIPT paths the system prompt (agent/system-prompt.md)
   references symbolically. Keeping per-session paths out of the system
   prompt keeps the prompt byte-identical across sessions, which is
   what lets providers serve it from prefix cache.
2. `fetch_resource_preview` — host-side CKAN schema prefetch that
   saves the agent its first 5-10 discovery calls.
3. `sanitize_content_html` — belt-and-braces cleanup for recurring
   LLM output failure modes (CDN script tags, fabricated SRI hashes,
   unclosed <script>/<style>, raw control chars in JS strings). Runs
   on every body before it can reach GCS.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import urlencode

log = logging.getLogger(__name__)


class ResourceRestrictedError(Exception):
    """The primary resource's CKAN datastore returns a 403 Authorization
    Error — the dataset's data is access-restricted upstream (private /
    de-listed). A build can't produce a real data page, and the 403 is
    deterministic (retrying won't help), so the caller marks the source
    `restricted` instead of burning an agent session or counting it as a
    transient failure."""


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


def _payload_is_authorization_error(payload: dict) -> bool:
    """True when a CKAN JSON envelope carries an Authorization Error.

    CKAN reports a restricted resource as `{"success": false, "error":
    {"__type": "Authorization Error", …}}` — surfaced either with HTTP 403
    or (rarely) HTTP 200.
    """
    err = payload.get("error") or {}
    return "Authorization" in str(err.get("__type") or "")


def _http_403_is_restriction(e: urllib_error.HTTPError) -> bool:
    """Decide whether a 403 from datastore_search is an access restriction.

    We send a browser User-Agent, so the gov.il WAF won't 403 us — a 403 here
    is the CKAN datastore Authorization Error. Confirm via the JSON body when
    it parses; if it doesn't, treat a bare 403 as a restriction anyway
    (rate-limiting is 429/503, never 403).
    """
    try:
        body = json.loads(e.read().decode("utf-8", errors="replace"))
    except Exception:
        return True
    return _payload_is_authorization_error(body)


def fetch_resource_preview(resource_id: str) -> Optional[dict]:
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
    payload: Optional[dict] = None
    for attempt in (1, 2):
        try:
            with urllib_request.urlopen(req, timeout=_PREFETCH_TIMEOUT_S) as resp:
                payload = json.loads(resp.read().decode("utf-8", errors="replace"))
            break
        except urllib_error.HTTPError as e:
            # A 403 here is a CKAN datastore Authorization Error — the data is
            # access-restricted upstream. Deterministic, so don't retry: signal
            # the caller to mark the source `restricted` rather than fall through
            # to an agent session that will only 403 again.
            if e.code == 403 and _http_403_is_restriction(e):
                raise ResourceRestrictedError(
                    f"CKAN datastore 403 (Authorization Error) for resource {resource_id}"
                ) from e
            last_err = e
            if attempt == 1:
                continue
        except (urllib_error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last_err = e
            if attempt == 1:
                continue
    else:
        log.warning(
            "ckan prefetch %s failed after retry: %s", resource_id[:8], last_err
        )
        return None
    if not payload or not payload.get("success"):
        # A 200 carrying the same Authorization Error is the restriction
        # surfaced differently — treat it identically to the 403 path.
        if payload and _payload_is_authorization_error(payload):
            raise ResourceRestrictedError(
                f"CKAN datastore Authorization Error for resource {resource_id}"
            )
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


def sanitize_content_html(body: str, *, dataset_id: str = "") -> str:
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


def build_user_message(
    *,
    dataset_id: str,
    title: str,
    notes: str,
    org_title: str,
    primary_resource_id: Optional[str],
    outputs_dir: str,
    check_script: str,
    pre_fetched_schema: Optional[dict] = None,
) -> str:
    resource_line = (
        f"primary_resource_id: {primary_resource_id}"
        if primary_resource_id
        else "primary_resource_id: (not pre-identified — pick one from package_show)"
    )
    od = outputs_dir.rstrip("/")
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
        f"to OUTPUTS_DIR, following the system prompt. All "
        "user-visible text in content.html must be Hebrew; your reasoning "
        "and bash commands can (and should) stay in English.\n\n"
        f"dataset_id: {dataset_id}\n"
        f"title (he): {title}\n"
        f"organization (he): {org_title or '(unknown)'}\n"
        f"description (he): {(notes or '(none)')[:1500]}\n"
        f"{resource_line}\n"
        f"OUTPUTS_DIR: {od}\n"
        f"CHECK_SCRIPT: {check_script}"
        f"{schema_block}\n\n"
        "Begin by investigating the dataset. When both files are written "
        "and the CHECK_SCRIPT self-check passes, stop."
    )


