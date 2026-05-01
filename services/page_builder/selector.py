"""Pick which source(s) the builder should process on this tick.

Priority (first non-empty track wins):
    1. `analysis_status == "never"`.
       Ordered by `metadata_modified` DESC.
    2. `change_status in {new, updated}` AND
       (`last_analyzed_at` is null OR older than `cooldown_days`).
       Ordered by CKAN `metadata_modified` DESC.

Backlog of never-analyzed sources is drained first — re-analyzing
already-published pages because CKAN flagged them as `updated` waits
until every source has at least one page.

The 14-day cooldown applies ONLY to Track 2 (already-analyzed sources
that CKAN just re-flagged as `updated`). For those, we skip a rebuild
if their last analysis happened less than 14 days ago, to avoid burning
agent budget on a page that's still fresh.

The cooldown does NOT apply to:
  - Never-analyzed sources (Track 1): always eligible, no matter how
    recently their CKAN row changed.
  - Sources whose `last_analyzed_at` is null: treated as never-analyzed
    for cooldown purposes.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.shared.firestore import FirestoreStateStore, SourceRecord

DEFAULT_COOLDOWN_DAYS = 14


def pick_next(
    store: FirestoreStateStore,
    n: int = 1,
    cooldown_days: int = DEFAULT_COOLDOWN_DAYS,
) -> list[SourceRecord]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=cooldown_days)
    picks: list[SourceRecord] = []
    seen: set[str] = set()

    # Track 1 — never analyzed. Drain the backlog before touching updates.
    for src in store.list_never_analyzed(limit=max(n * 4, 16)):
        if src.id in seen:
            continue
        picks.append(src)
        seen.add(src.id)
        if len(picks) >= n:
            return picks

    # Track 2 — already analyzed, CKAN-updated, past cooldown.
    if len(picks) < n:
        for src in store.list_changed_sources(limit=max((n - len(picks)) * 4, 16)):
            if src.id in seen:
                continue
            if src.last_analyzed_at is None or _as_utc(src.last_analyzed_at) < cutoff:
                picks.append(src)
                seen.add(src.id)
                if len(picks) >= n:
                    break

    return picks


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
