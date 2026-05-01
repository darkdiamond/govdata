"""Pick which source(s) the builder should process on this tick.

Priority (first non-empty track wins):
    1. `change_status in {new, updated}` AND
       (`last_analyzed_at` is null OR older than `cooldown_days`).
       Ordered by CKAN `metadata_modified` DESC.
    2. `analysis_status == "never"`.
       Ordered by `metadata_modified` DESC.

The 14-day cooldown applies ONLY to sources that have already been
analyzed at least once AND have just been updated upstream on data.gov.il
(Track 1). For those, we skip a rebuild if their last analysis happened
less than 14 days ago — even if CKAN flagged the source as `updated`.
This prevents re-burning agent budget on a source that just got a fresh
page.

The cooldown does NOT apply to:
  - Never-analyzed sources (Track 2): always eligible, no matter how
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

    # Track 1 — changed and past cooldown.
    for src in store.list_changed_sources(limit=max(n * 4, 16)):
        if src.id in seen:
            continue
        if src.last_analyzed_at is None or _as_utc(src.last_analyzed_at) < cutoff:
            picks.append(src)
            seen.add(src.id)
            if len(picks) >= n:
                return picks

    # Track 2 — never analyzed (may overlap with Track 1 candidates already picked).
    if len(picks) < n:
        for src in store.list_never_analyzed(limit=max((n - len(picks)) * 4, 16)):
            if src.id in seen:
                continue
            picks.append(src)
            seen.add(src.id)
            if len(picks) >= n:
                break

    return picks


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
