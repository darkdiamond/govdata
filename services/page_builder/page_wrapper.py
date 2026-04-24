"""Render a full dataset page from agent-authored content + manifest data.

Inputs:
    content.html  — body content the agent wrote (goes inside <main>)
    ManifestEntry — this dataset's data.json
    related       — list of ManifestEntry for the sidebar (controller computes)

Output: one complete HTML string ready to upload to `/datasets/<id>/index.html`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .schema import ManifestEntry

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True, lstrip_blocks=True,
)

_KIND_LABELS_HE = {
    "map": "גיאוגרפי",
    "timeseries": "סדרת זמן",
    "registry": "רשימת ישויות",
    "rankings": "דירוגים",
    "misc": "אחר",
}


def _short(text: str, n: int = 160) -> str:
    text = (text or "").strip().replace("\n", " ")
    return text if len(text) <= n else text[:n - 1] + "…"


def wrap_page(
    *,
    content_html: str,
    entry: ManifestEntry,
    related: list[ManifestEntry],
) -> str:
    """Render a full HTML page. `content_html` is injected verbatim as the
    `<main>` body (including any inline `<style>` / `<script>` tags the agent
    emitted — they're marked safe)."""
    template = _env.get_template("dataset_page.html.j2")
    return template.render(
        entry=entry,
        related=related,
        content=content_html,
        description=_short(entry.summary_he or entry.title, 160),
        kind_label=_KIND_LABELS_HE.get(entry.dataset_kind or "misc", "אחר"),
        year=datetime.now(timezone.utc).year,
    )
