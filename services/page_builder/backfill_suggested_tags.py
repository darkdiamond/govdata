"""One-off backfill: populate `agent_data.suggested_tags` for sources
that were analyzed before the `suggested_tags` field existed.

The agent used to render its tag chips inline as
`<span class="tag-chip">…</span>` blocks in `content.html`. Going
forward the chip taxonomy lives in `agent_data.suggested_tags` and the
frontend shell injects the row. This script extracts the chip text from
each existing `frontend/public/datasets/<id>/content.html` and writes
the resulting list onto the Firestore source doc — no agent re-runs.

Run against prod Firestore directly (per the project memory), in small
batches:

    # Dry-run first — show what would be written.
    python -m services.page_builder.backfill_suggested_tags --dry-run

    # Single-source smoke.
    python -m services.page_builder.backfill_suggested_tags --source <id>

    # Full backfill.
    python -m services.page_builder.backfill_suggested_tags
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path
from typing import Optional

from services.shared.firestore import FirestoreStateStore, SourceRecord

log = logging.getLogger(__name__)


_CHIP_RE = re.compile(
    r'<span\s+class="tag-chip"\s*>([^<]+)</span>',
    re.IGNORECASE,
)


def extract_chip_texts(html: str, *, max_tags: int = 8) -> list[str]:
    """Pull tag-chip text out of an agent-emitted body, dedup-preserving-order."""
    seen: list[str] = []
    seen_set: set[str] = set()
    for raw in _CHIP_RE.findall(html):
        text = raw.strip()
        if not text or text in seen_set:
            continue
        seen.append(text)
        seen_set.add(text)
        if len(seen) >= max_tags:
            break
    return seen


def _content_html_path(public_root: Path, dataset_id: str) -> Path:
    return public_root / "datasets" / dataset_id / "content.html"


def needs_backfill(src: SourceRecord) -> bool:
    """A source needs backfill when it's been analyzed but has no
    `suggested_tags` yet."""
    if src.analysis_status != "succeeded":
        return False
    agent_data = src.agent_data or {}
    existing = agent_data.get("suggested_tags") or []
    return not existing


def backfill_one(
    src: SourceRecord,
    *,
    public_root: Path,
    store: FirestoreStateStore,
    dry_run: bool,
) -> Optional[list[str]]:
    """Returns the list of tags written (or that would be written), or
    None if the source was skipped."""
    html_path = _content_html_path(public_root, src.id)
    if not html_path.exists():
        log.debug("skip %s: no content.html at %s", src.id, html_path)
        return None
    html = html_path.read_text(encoding="utf-8")
    tags = extract_chip_texts(html)
    if not tags:
        log.debug("skip %s: no tag-chip spans found", src.id)
        return None
    if dry_run:
        return tags
    # Merge into existing agent_data so we don't trample summary_he/etc.
    new_agent_data = dict(src.agent_data or {})
    new_agent_data["suggested_tags"] = tags
    store.set_agent_data(src.id, new_agent_data)
    return tags


def run(
    *,
    public_root: Path,
    only_source: Optional[str] = None,
    dry_run: bool = False,
    limit: Optional[int] = None,
) -> dict:
    store = FirestoreStateStore()

    if only_source is not None:
        src = store.get_source(only_source)
        if src is None:
            log.error("source %s not found", only_source)
            return {"updated": 0, "skipped": 0, "missing": 1}
        sources: list[SourceRecord] = [src]
    else:
        sources = [s for s in store.iter_succeeded_sources() if needs_backfill(s)]

    log.info(
        "backfill: %d candidate source(s)%s",
        len(sources),
        " (dry-run)" if dry_run else "",
    )

    updated = 0
    skipped = 0
    examples: list[tuple[str, list[str]]] = []
    for i, src in enumerate(sources):
        if limit is not None and i >= limit:
            break
        tags = backfill_one(
            src, public_root=public_root, store=store, dry_run=dry_run
        )
        if tags is None:
            skipped += 1
            continue
        updated += 1
        if len(examples) < 10:
            examples.append((src.id, tags))

    if dry_run or only_source is not None:
        for sid, tags in examples:
            print(f"{sid}: {tags}")

    return {"updated": updated, "skipped": skipped}


def _cli() -> int:
    p = argparse.ArgumentParser(
        description="Backfill agent_data.suggested_tags from existing content.html.",
    )
    p.add_argument(
        "--public-root",
        default="frontend/public",
        help="Root of the deployed frontend (default: frontend/public).",
    )
    p.add_argument("--source", help="Only backfill this dataset id.")
    p.add_argument("--dry-run", action="store_true", help="Print, don't write.")
    p.add_argument("--limit", type=int, help="Cap the number of sources processed.")
    p.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose logging."
    )
    args = p.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    public_root = Path(args.public_root)
    if not public_root.exists():
        log.error("public root %s does not exist", public_root)
        return 1

    summary = run(
        public_root=public_root,
        only_source=args.source,
        dry_run=args.dry_run,
        limit=args.limit,
    )
    log.info("backfill done: %s", summary)
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
