"""One-shot CLI: backfill Voyage embeddings for already-succeeded sources.

The publisher embeds new sources lazily during publish, so this CLI is only
needed once — to retro-fill the corpus that was published before
VOYAGE_API_KEY was wired into Cloud Run. Re-runs are safe: any source that
already has an embedding is skipped.

Usage:
    source venv/bin/activate
    export VOYAGE_API_KEY=<key>     # local shell only
    python -m services.page_builder.backfill_embeddings --dry-run
    python -m services.page_builder.backfill_embeddings --limit 3
    python -m services.page_builder.backfill_embeddings
"""
from __future__ import annotations

import argparse
import json
import logging
from typing import Iterable

from services.shared.firestore import FirestoreStateStore, SourceRecord

from .embeddings import embed_batch, embedding_input

log = logging.getLogger(__name__)

CHUNK_SIZE = 128


def _compose_text(src: SourceRecord) -> str:
    org_title = (src.organization or {}).get("title")
    summary_he = (src.agent_data or {}).get("summary_he")
    return embedding_input(
        title=src.title,
        summary_he=summary_he,
        organization=org_title,
        tags_he=list(src.tags or []),
    )


def _chunks(seq: list, size: int) -> Iterable[list]:
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def backfill(*, dry_run: bool = False, limit: int | None = None,
             store: FirestoreStateStore | None = None) -> dict:
    store = store or FirestoreStateStore()
    succeeded = list(store.iter_succeeded_sources())
    pending = [r for r in succeeded if not r.embedding and r.agent_data]
    if limit is not None:
        pending = pending[:limit]

    log.info(
        "backfill: %d succeeded, %d already embedded, %d pending%s",
        len(succeeded),
        sum(1 for r in succeeded if r.embedding),
        len(pending),
        " (dry-run)" if dry_run else "",
    )
    for r in pending:
        log.info("  pending: %s — %s", r.id, r.title)

    if dry_run or not pending:
        return {
            "succeeded": len(succeeded),
            "pending": len(pending),
            "embedded": 0,
            "failed": 0,
        }

    embedded = 0
    failed = 0
    for chunk in _chunks(pending, CHUNK_SIZE):
        texts = [_compose_text(r) for r in chunk]
        vectors = embed_batch(texts)
        for src, vec in zip(chunk, vectors):
            if vec is None:
                failed += 1
                log.warning("  embed failed: %s", src.id)
                continue
            store.set_embedding(src.id, vec)
            embedded += 1
            log.info("  embedded: %s (dim=%d)", src.id, len(vec))

    return {
        "succeeded": len(succeeded),
        "pending": len(pending),
        "embedded": embedded,
        "failed": failed,
    }


def _cli() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true",
                   help="List sources that need embedding; don't call Voyage or write Firestore.")
    p.add_argument("--limit", type=int, default=None,
                   help="Embed at most N sources (smoke-test).")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    summary = backfill(dry_run=args.dry_run, limit=args.limit)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    _cli()
