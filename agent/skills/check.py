#!/usr/bin/env python3
"""Self-check for agent-emitted content.html + agent_data.json.

Invoked by the agent before end_turn:
    python3 /workspace/check.py content.html agent_data.json

Exits 0 with "OK" on success; non-zero with a one-line diagnostic on
failure. The agent fixes the offending file and re-runs.

This script is the single source of truth for the post-output rules
listed in the system prompt. The publisher's `_sanitize_content_html`
auto-fixes a subset (CDN scripts, escaped </script>, integrity attrs,
unbalanced tags, JS-string control chars), but does NOT cover the
quality/truth classes here — palette correctness, Heebo refs, max-w-*
outers, missing icon headers, missing <ul>/<li> insights, the 50KB
inline-data cap, percent-conflict across year contexts. Hence the
runtime check.

Copied into each session's private workdir (CHECK_SCRIPT in
services/page_builder/agent_contract.py) so the agent can self-check
in-session, and run again host-side on the sanitized body by
services/page_builder/agent_runner.py before anything persists.
"""
from __future__ import annotations

import json
import re
import sys

VALID_DATASET_KINDS = {"map", "timeseries", "registry", "rankings", "misc"}

# HTML hygiene — combined regex for forbidden tags / attrs / classes /
# colors / hosts. Keeping these in one pass mirrors the original bash
# grep so a regression on any one of them is reported with the same
# message.
HYGIENE_RE = re.compile(
    r"<(?:html|head|body|header|footer|nav)\b"
    r"|<link\b"
    r"|<script[^>]*\bsrc="
    r'|\bintegrity\s*='
    r"|\bcrossorigin\b"
    r"|<\\/script"
    r'|class="[^"]*\bmax-w-(?:6xl|7xl|3xl|4xl|5xl|full)\b'
    r"|#(?:6f42c1|856404|fd7e14|e83e8c|20c997|6610f2|d63384|0B3D91|EAB308|FAFAF7)"
    r"|\bHeebo\b"
    r"|https?://e\.data\.gov\.il"
    r"|<h3[^>]*>\s*(?:פרטים|משאבים)\s*</h3>"
)
INLINE_STYLE_RE = re.compile(r'style="[^"]*\b(?:line-height|color)\s*:')
SPACING_RHYTHM_RE = re.compile(
    r'class="[^"]*\bcard\b[^"]*\bp-5\b[^"]*\bmb-(?:[0-57-9]|[0-9]{2,})\b'
)
# Legacy geresh trap (two consecutive gereshes after a Hebrew letter).
GERESH_RE = re.compile(r"[א-ת]''")

# The shell renders the data explorer (search + paginated table with
# server-side full-text search) below the agent's content for every
# datastore-active resource. Agent output must not build its own:
# no GovExplorer calls, no id="explorer…" elements.
EXPLORER_RE = re.compile(r'\bGovExplorer\b|\bid="explorer')

SCRIPT_BLOCK_RE = re.compile(
    r"<script\b[^>]*>(.*?)</script\s*>", re.DOTALL | re.IGNORECASE
)

TOP_CARD_BARE_H2_RE = re.compile(
    r'<section\s+class="[^"]*\bcard\b[^"]*\bmb-6\b[^"]*"[^>]*>\s*<h2',
    re.IGNORECASE | re.DOTALL,
)

INSIGHT_HEADING_RE = re.compile(r"<h2[^>]*>\s*(?:תובנות|ממצאים)[^<]*</h2>")
LI_RE = re.compile(r"<li\b[^>]*>(.*?)</li>", re.DOTALL | re.IGNORECASE)
UL_OPEN_RE = re.compile(r"<ul\b([^>]*)>")

LINE_TERM = "\n\r  "


def fail(msg: str, code: int = 1) -> "None":
    print(msg)
    sys.exit(code)


def check_html_hygiene(body: str) -> None:
    m = HYGIENE_RE.search(body)
    if m:
        fail(f"HYGIENE: forbidden token near {body[max(0,m.start()-20):m.end()+20]!r}")
    m = INLINE_STYLE_RE.search(body)
    if m:
        fail(
            "INLINE-STYLE: line-height / color belong on Tailwind utilities, "
            f"not inline style — near {body[max(0,m.start()-20):m.end()+40]!r}"
        )
    m = SPACING_RHYTHM_RE.search(body)
    if m:
        fail(
            "SPACING-RHYTHM: top-level card.p-5 blocks must use mb-6 — "
            f"found mb-N != 6 near {body[max(0,m.start()-10):m.end()+10]!r}"
        )
    m = GERESH_RE.search(body)
    if m:
        fail(
            "GERESH-TRAP: legacy two-consecutive-geresh after Hebrew letter — "
            f"near {body[max(0,m.start()-10):m.end()+10]!r}"
        )
    m = EXPLORER_RE.search(body)
    if m:
        fail(
            "SHELL-EXPLORER: the shell renders the data explorer — remove "
            f'GovExplorer / id="explorer…" near {body[max(0,m.start()-20):m.end()+40]!r}'
        )


def check_inline_data_cap(blocks: list[str]) -> None:
    # Any single <script> block over 50 KB means a row dump was inlined
    # into HTML. Use GovMap for point-set maps; row browsing is provided
    # by the shell — compute aggregates in Python instead.
    for i, b in enumerate(blocks, 1):
        if len(b) > 51_200:
            fail(
                f"INLINE-DATA: <script> block #{i} is {len(b)} bytes (>50KB cap). "
                "Use GovMap for point maps; row browsing is provided by the "
                "shell — compute aggregates in Python instead.",
                code=1,
            )


_SMOOTH_TRUE = re.compile(r"\bsmooth\s*:\s*true\b")


def check_no_spline(blocks: list[str]) -> None:
    # Line charts render measured values, not curves: spline smoothing
    # interpolates values that were never measured and rounds off real
    # peaks. The prompt forbids `smooth: true`; enforce it here.
    for i, b in enumerate(blocks, 1):
        m = _SMOOTH_TRUE.search(b)
        if m:
            fail(
                f"SPLINE: <script> block #{i} sets `smooth: true` — line "
                "charts must use straight segments (remove the smooth "
                "option entirely).",
                code=1,
            )


def check_js_string_hygiene(blocks: list[str]) -> None:
    # Walks each script block tracking comment / string state, mirroring
    # the publisher's sanitizer. Catches:
    #   (a) bare geresh after a Hebrew letter inside a single-quoted
    #       string — closes the literal early, kills the IIFE.
    #   (b) raw line terminator (LF/CR/U+2028/U+2029) inside a "…"/'…'
    #       string — V8 syntax error, blanks every chart.
    for n, src in enumerate(blocks, 1):
        i, L = 0, len(src)
        while i < L:
            c = src[i]
            if c == "/" and i + 1 < L and src[i + 1] == "/":
                j = src.find("\n", i)
                i = L if j < 0 else j
                continue
            if c == "/" and i + 1 < L and src[i + 1] == "*":
                j = src.find("*/", i + 2)
                i = L if j < 0 else j + 2
                continue
            if c == "`":
                i += 1
                while i < L:
                    if src[i] == "\\" and i + 1 < L:
                        i += 2
                        continue
                    if src[i] == "`":
                        i += 1
                        break
                    i += 1
                continue
            if c == '"' or c == "'":
                q = c
                start = i
                i += 1
                while i < L:
                    ch = src[i]
                    if ch == "\\" and i + 1 < L:
                        i += 2
                        continue
                    if ch == q:
                        i += 1
                        break
                    if ch in LINE_TERM:
                        fail(
                            f"CTRL-CHAR-IN-JS-STR (script #{n}): "
                            f"{src[start:i][:80]!r} contains raw line terminator. "
                            "JSON.stringify the value or move it out of the string.",
                            code=3,
                        )
                    if (
                        q == "'"
                        and re.match(r"[א-ת]", ch)
                        and i + 1 < L
                        and src[i + 1] == "'"
                    ):
                        fail(
                            f"GERESH-IN-SQ-STR (script #{n}): single-quoted JS "
                            f"string contains Hebrew+geresh near "
                            f"{src[max(0,i-10):i+5]!r}. Use a double-quoted "
                            "string or escape with \\\\'.",
                            code=4,
                        )
                    i += 1
                continue
            i += 1


_CATEGORY_YAXIS_RE = re.compile(r"yAxis\s*:\s*\{[^}]*['\"]category['\"]")
_LABEL_POS_LEFT_RE = re.compile(r"position\s*:\s*['\"]left['\"]")


def check_hbar_label_position(blocks: list[str]) -> None:
    # Horizontal bars (category yAxis) grow left→right; a value label at
    # position 'left' sits at the bar's BASE, on top of the y-axis
    # category names (ECharts positions are geometric even on RTL
    # pages). The bar's end is 'right' / 'insideRight'.
    for i, b in enumerate(blocks, 1):
        # Per-chart granularity: a block often holds several setOption
        # calls, and `position: 'left'` is legitimate on other chart
        # types — only flag it inside the same chart config as a
        # category yAxis.
        segments = re.split(r"\.setOption\(", b)[1:] or [b]
        for seg in segments:
            if _CATEGORY_YAXIS_RE.search(seg) and _LABEL_POS_LEFT_RE.search(seg):
                fail(
                    f"HBAR-LABEL: <script> block #{i} has a horizontal bar "
                    "(category yAxis) with a label `position: 'left'` — the "
                    "value lands on the category names. Use `position: "
                    "'right'` (or 'insideRight' for near-max bars).",
                    code=6,
                )


_FMT_HELPER_DEF_RE = re.compile(
    r"function\s+(\w+)\s*\(\s*(\w+)\s*\)\s*\{\s*return\s+(\w+)\s*"
    r"\.to(?:LocaleString|Fixed)"
)
_FMT_ARROW_DEF_RE = re.compile(
    r"(?:var|let|const)\s+(\w+)\s*=\s*\(?\s*(\w+)\s*\)?\s*=>\s*(\w+)\s*"
    r"\.to(?:LocaleString|Fixed)"
)
_FMT_INLINE_RE = re.compile(
    r"label\s*:\s*\{[^{}]*formatter\s*:\s*"
    r"(?:function\s*\(\s*(\w+)\s*\)\s*\{\s*return\s+(\w+)\s*\.to(?:LocaleString|Fixed)"
    r"|\(?\s*(\w+)\s*\)?\s*=>\s*(\w+)\s*\.to(?:LocaleString|Fixed))"
)


def check_label_formatter_params(blocks: list[str]) -> None:
    # ECharts label formatters receive a params OBJECT, not the value.
    # A raw-value helper (`function numFmt(v){ return v.toLocaleString }`)
    # passed as `label.formatter` renders "[object Object]" on every bar.
    # Format `p.value` instead.
    msg = (
        "FMT-PARAMS: <script> block #%d passes a raw-value number "
        "formatter as a label formatter — ECharts calls it with a params "
        "OBJECT, rendering '[object Object]'. Use "
        "`formatter: function(p){ return numFmt(p.value); }`."
    )
    for i, b in enumerate(blocks, 1):
        m = _FMT_INLINE_RE.search(b)
        if m and (
            (m.group(1) and m.group(1) == m.group(2))
            or (m.group(3) and m.group(3) == m.group(4))
        ):
            fail(msg % i, code=7)
        helpers = {
            m.group(1)
            for m in _FMT_HELPER_DEF_RE.finditer(b)
            if m.group(2) == m.group(3)
        } | {
            m.group(1)
            for m in _FMT_ARROW_DEF_RE.finditer(b)
            if m.group(2) == m.group(3)
        }
        for h in helpers:
            if re.search(
                r"label\s*:\s*\{[^{}]*formatter\s*:\s*" + re.escape(h) + r"\s*[,}]", b
            ):
                fail(msg % i, code=7)


_OPENERS = {"(": ")", "[": "]", "{": "}"}
_CLOSERS = {")": "(", "]": "[", "}": "{"}
# A `/` whose last significant code char is one of these starts a regex
# literal, not division. Heuristic, but reliable for chart-config code.
_REGEX_PRECEDERS = set("=([{,;:!&|?+-*/%<>~^")


def check_js_delimiter_balance(blocks: list[str]) -> None:
    # One extra or missing bracket/brace/paren anywhere in a script block
    # is a page-killing V8 SyntaxError that no other rule catches (e.g. a
    # stray `}` inside a setOption argument). Walk code outside strings /
    # comments / regex literals and require the three delimiter kinds to
    # nest correctly.
    for n, src in enumerate(blocks, 1):
        stack: list = []
        prev = ""  # last significant code char seen
        i, L = 0, len(src)
        while i < L:
            c = src[i]
            if c == "/" and i + 1 < L and src[i + 1] == "/":
                j = src.find("\n", i)
                i = L if j < 0 else j
                continue
            if c == "/" and i + 1 < L and src[i + 1] == "*":
                j = src.find("*/", i + 2)
                i = L if j < 0 else j + 2
                continue
            if c == "/" and (not prev or prev in _REGEX_PRECEDERS):
                # Regex literal: skip to the unescaped closing `/`; inside
                # a [...] character class `/` doesn't close. A newline
                # before the close means it wasn't a regex — stop skipping.
                i += 1
                in_class = False
                while i < L:
                    ch = src[i]
                    if ch == "\\" and i + 1 < L:
                        i += 2
                        continue
                    if ch == "[":
                        in_class = True
                    elif ch == "]":
                        in_class = False
                    elif ch == "/" and not in_class:
                        i += 1
                        break
                    elif ch == "\n":
                        break
                    i += 1
                prev = "/"
                continue
            if c == "`":
                i += 1
                while i < L:
                    if src[i] == "\\" and i + 1 < L:
                        i += 2
                        continue
                    if src[i] == "`":
                        i += 1
                        break
                    i += 1
                prev = "`"
                continue
            if c == '"' or c == "'":
                q = c
                i += 1
                while i < L:
                    if src[i] == "\\" and i + 1 < L:
                        i += 2
                        continue
                    if src[i] == q:
                        i += 1
                        break
                    i += 1
                prev = q
                continue
            if c in _OPENERS:
                stack.append((c, i))
            elif c in _CLOSERS:
                if not stack or stack[-1][0] != _CLOSERS[c]:
                    fail(
                        f"JS-BALANCE (script #{n}): unexpected {c!r} near "
                        f"{src[max(0, i - 60):i + 20]!r} — an extra or "
                        "misplaced bracket breaks the whole script.",
                        code=5,
                    )
                stack.pop()
            if not c.isspace():
                prev = c
            i += 1
        if stack:
            ch, pos = stack[-1]
            fail(
                f"JS-BALANCE (script #{n}): {ch!r} opened near "
                f"{src[max(0, pos - 40):pos + 40]!r} is never closed.",
                code=5,
            )


def check_icon_headers(body: str) -> None:
    # Top-level <section class="card ... mb-6"> must open with the
    # icon-paired flex wrapper, not a bare <h2>. Sub-cards inside grids
    # (no mb-6) are exempt.
    m = TOP_CARD_BARE_H2_RE.search(body)
    if m:
        fail(
            "MISSING-ICON-HEADER: top-level card opens with bare <h2> instead "
            'of <div class="flex items-center gap-2 mb-3 text-brand">'
            '<img src="/icons/<name>.svg" .../><h2.../></div>. Near '
            f"{body[m.start():m.start()+120]!r}",
            code=5,
        )


def check_insights(body: str) -> None:
    # The תובנות / ממצאים section MUST contain <ul> with at least one <li>;
    # the <ul> must use list-disc (Tailwind restores the disc bullet) OR
    # every <li> must contain its own <img> icon — otherwise Tailwind's
    # preflight strips the marker and the items are visually invisible.
    for m in INSIGHT_HEADING_RE.finditer(body):
        sec_start = body.rfind("<section", 0, m.start())
        sec_end = body.find("</section>", m.end())
        if sec_start < 0 or sec_end < 0:
            fail(
                f"INSIGHTS-NOT-IN-SECTION: heading at byte {m.start()} is "
                "not wrapped in <section>...</section>",
                code=6,
            )
        chunk = body[sec_start:sec_end]
        if "<ul" not in chunk or "<li" not in chunk:
            fail(
                f"INSIGHTS-NO-BULLETS: תובנות/ממצאים section at byte "
                f"{sec_start} has no <ul>/<li>. Use "
                '<ul class="list-disc ps-5 m-0 space-y-2 text-sm '
                'marker:text-brand"><li>…</li></ul>.',
                code=7,
            )
        ul = UL_OPEN_RE.search(chunk)
        if ul:
            ul_attrs = ul.group(1)
            if "list-disc" not in ul_attrs and "list-decimal" not in ul_attrs:
                items = LI_RE.findall(chunk)
                bad = [i for i, it in enumerate(items) if "<img" not in it.lower()]
                if bad:
                    fail(
                        "INSIGHTS-NO-MARKER: <ul> in תובנות/ממצאים has neither "
                        "`list-disc` (with optional `marker:text-brand`) nor "
                        "an <img> inside every <li>. Tailwind preflight kills "
                        "default bullets — pick one of the two patterns from "
                        f"BODY SKELETON. Bad <li> indices: {bad[:3]}",
                        code=8,
                    )


def check_percent_consistency(body: str) -> None:
    # Same % appearing >=2 times with conflicting year contexts.
    # Cross-paragraph "different %s for same trend" cases are NOT
    # detected — reconcile those by reading both yourself.
    YEAR_RE = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")
    pcts = re.findall(r"(\d+(?:[.,]\d+)?)\s*%", body)
    seen: dict[str, int] = {}
    for p in pcts:
        seen[p] = seen.get(p, 0) + 1
    for p, n in sorted(seen.items()):
        if n < 2:
            continue
        year_sets = []
        for m in re.finditer(rf"(.{{0,60}}){re.escape(p)}\s*%(.{{0,60}})", body):
            ctx = m.group(1) + p + "%" + m.group(2)
            years = YEAR_RE.findall(ctx)
            if years:
                year_sets.append(tuple(sorted(set(years))))
        if len(set(year_sets)) >= 2:
            fail(
                f"PERCENT-CONFLICT: {p}% appears {n}x with conflicting year "
                f"contexts {year_sets}",
                code=2,
            )


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(f"usage: {argv[0]} content.html agent_data.json", file=sys.stderr)
        return 64
    html_path, json_path = argv[1], argv[2]

    with open(html_path, encoding="utf-8") as f:
        body = f.read()
    with open(json_path, encoding="utf-8") as f:
        d = json.load(f)

    # agent_data.json shape
    if not d.get("summary_he"):
        fail("AGENT-DATA: summary_he missing or empty")
    if d.get("dataset_kind") not in VALID_DATASET_KINDS:
        fail(f"AGENT-DATA: dataset_kind invalid: {d.get('dataset_kind')!r}")
    suggested = d.get("suggested_tags") or []
    if not isinstance(suggested, list) or not (1 <= len(suggested) <= 8):
        fail(
            f"AGENT-DATA: suggested_tags must be a list of 1-8 short Hebrew "
            f"topic labels, got {suggested!r}"
        )
    if any(not isinstance(t, str) or not t.strip() for t in suggested):
        fail("AGENT-DATA: suggested_tags entries must be non-empty strings")

    check_html_hygiene(body)

    blocks = SCRIPT_BLOCK_RE.findall(body)
    check_inline_data_cap(blocks)
    check_no_spline(blocks)
    check_js_string_hygiene(blocks)
    check_js_delimiter_balance(blocks)
    check_hbar_label_position(blocks)
    check_label_formatter_params(blocks)

    check_icon_headers(body)
    check_insights(body)
    check_percent_consistency(body)

    print(f"OK {d['dataset_kind']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
