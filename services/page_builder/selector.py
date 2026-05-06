"""Pick which source(s) the builder should process on this tick.

Priority (first non-empty track wins):
    1. `analysis_status == "never"`.
       Ordered by `metadata_modified` DESC.
    2. `change_status in {new, updated}` AND
       (`last_analyzed_at` is null OR older than `cooldown_days`).
       Ordered by CKAN `metadata_modified` DESC.

Both tracks are gated by an effective cutoff = `max(min_modified_floor,
now - max_age_days)`. A source is only eligible if its CKAN
`metadata_modified` is on/after that cutoff.

Two gates compose:
  - **Fixed floor** (`min_modified_floor`, default 2026-01-01): we don't
    publish pages for datasets last touched before this date, period.
    Anchors the corpus to the current era of gov.il data.
  - **Rolling window** (`max_age_days`, default 365): a source untouched
    for over a year is usually archival/abandoned, expensive to analyze,
    and unlikely to interest readers.

Today the floor wins (2026-01-01 is more recent than now-365d). As time
moves on, the rolling window will eventually overtake the floor and
become the binding constraint — at which point pages from early 2026
start aging out naturally.

Backlog of (recent) never-analyzed sources is drained first — re-analyzing
already-published pages because CKAN flagged them as `updated` waits
until every recent source has at least one page.

The 14-day cooldown applies ONLY to Track 2 (already-analyzed sources
that CKAN just re-flagged as `updated`). For those, we skip a rebuild
if their last analysis happened less than 14 days ago, to avoid burning
agent budget on a page that's still fresh.

The cooldown does NOT apply to:
  - Never-analyzed sources (Track 1): always eligible (within cutoff),
    no matter how recently their CKAN row changed.
  - Sources whose `last_analyzed_at` is null: treated as never-analyzed
    for cooldown purposes.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.shared.firestore import FirestoreStateStore, SourceRecord

DEFAULT_COOLDOWN_DAYS = 14
DEFAULT_MAX_AGE_DAYS = 365
DEFAULT_MIN_MODIFIED_FLOOR = datetime(2026, 1, 1, tzinfo=timezone.utc)


def pick_next(
    store: FirestoreStateStore,
    n: int = 1,
    cooldown_days: int = DEFAULT_COOLDOWN_DAYS,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    min_modified_floor: datetime = DEFAULT_MIN_MODIFIED_FLOOR,
) -> list[SourceRecord]:
    now = datetime.now(timezone.utc)
    cooldown_cutoff = now - timedelta(days=cooldown_days)
    age_cutoff = max(now - timedelta(days=max_age_days), _as_utc(min_modified_floor))
    picks: list[SourceRecord] = []
    seen: set[str] = set()

    # Track 1 — never analyzed AND `metadata_modified >= age_cutoff`.
    # Both store queries return rows ordered by `metadata_modified` DESC, so
    # once we hit a row past `age_cutoff` every remaining row is also too old.
    for src in store.list_never_analyzed(limit=max(n * 4, 16)):
        if src.id in seen:
            continue
        if src.metadata_modified is None or _as_utc(src.metadata_modified) < age_cutoff:
            break
        picks.append(src)
        seen.add(src.id)
        if len(picks) >= n:
            return picks

    # Track 2 — already analyzed, CKAN-updated, past cooldown, within max_age.
    if len(picks) < n:
        for src in store.list_changed_sources(limit=max((n - len(picks)) * 4, 16)):
            if src.id in seen:
                continue
            if src.metadata_modified is None or _as_utc(src.metadata_modified) < age_cutoff:
                break
            if src.last_analyzed_at is None or _as_utc(src.last_analyzed_at) < cooldown_cutoff:
                picks.append(src)
                seen.add(src.id)
                if len(picks) >= n:
                    break

    return picks


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
