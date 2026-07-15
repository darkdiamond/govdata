"""Tests for services.page_builder.selector.pick_next.

Regression for the sticky `change_status` bug: the scanner only writes
`change_status` on NEW/UPDATED and nothing ever resets it after a
successful analysis, so a source flagged `updated` once stays in the
Track 2 candidate set forever. Track 2 must therefore skip sources whose
live CKAN `metadata_modified` hasn't advanced past the version already
analyzed (`analyzed_metadata_modified`) — otherwise every published page
gets a full agent re-run every cooldown period, forever.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from services.page_builder.selector import pick_next
from services.shared.firestore import SourceRecord

# Past the 2026-01-01 floor so the age gate never interferes.
MODIFIED = datetime(2026, 5, 1, tzinfo=timezone.utc)


def _track2_src(
    dataset_id: str,
    *,
    metadata_modified: datetime = MODIFIED,
    analyzed_metadata_modified: datetime | None = None,
    last_analyzed_days_ago: int = 60,
) -> SourceRecord:
    return SourceRecord(
        id=dataset_id,
        title="מאגר לדוגמה",
        metadata_modified=metadata_modified,
        analyzed_metadata_modified=analyzed_metadata_modified,
        # Pinned relative to MODIFIED (not "now"): the Track 2 gate
        # compares metadata_modified against last_analyzed_at directly.
        last_analyzed_at=MODIFIED - timedelta(days=last_analyzed_days_ago),
        analysis_status="succeeded",
        change_status="updated",
    )


def _store(track2: list[SourceRecord]) -> MagicMock:
    store = MagicMock()
    store.list_never_analyzed.return_value = []
    store.list_changed_sources.return_value = track2
    return store


def test_track2_skips_source_already_analyzed_at_current_version():
    """metadata_modified == analyzed_metadata_modified ⇒ nothing changed
    since the page was built; the sticky `updated` flag must not trigger
    another agent run."""
    src = _track2_src("stale-flag", analyzed_metadata_modified=MODIFIED)
    assert pick_next(_store([src]), n=5) == []


def test_track2_picks_source_when_ckan_advanced_past_analysis():
    src = _track2_src(
        "really-updated",
        metadata_modified=MODIFIED + timedelta(days=3),
        analyzed_metadata_modified=MODIFIED,
    )
    picks = pick_next(_store([src]), n=5)
    assert [s.id for s in picks] == ["really-updated"]


def test_track2_legacy_source_without_analyzed_marker_stays_eligible():
    """Docs analyzed before `analyzed_metadata_modified` existed have it
    as None — we can't tell whether they changed, so keep old behavior."""
    src = _track2_src("legacy", analyzed_metadata_modified=None)
    picks = pick_next(_store([src]), n=5)
    assert [s.id for s in picks] == ["legacy"]


def test_reanalyze_false_pauses_track2_entirely():
    """REANALYZE_ENABLED=false stopgap: until structural-vs-additive change
    gating exists, daily-append datasets re-qualify every cooldown period;
    the knob lets us pause all Track 2 re-runs without touching Track 1."""
    src = _track2_src(
        "would-be-picked",
        metadata_modified=MODIFIED + timedelta(days=3),
        analyzed_metadata_modified=MODIFIED,
    )
    store = _store([src])
    assert pick_next(store, n=5, reanalyze=False) == []
    store.list_changed_sources.assert_not_called()


def test_reanalyze_false_keeps_track1():
    never = SourceRecord(
        id="brand-new",
        title="חדש",
        metadata_modified=MODIFIED,
        analysis_status="never",
        change_status="new",
    )
    store = MagicMock()
    store.list_never_analyzed.return_value = [never]
    store.list_changed_sources.return_value = []
    picks = pick_next(store, n=5, reanalyze=False)
    assert [s.id for s in picks] == ["brand-new"]


def _gap_src(
    dataset_id: str, *, updated_days_after_analysis: int
) -> SourceRecord:
    """CKAN advanced past our build by the given number of days.

    `last_analyzed_at` is pinned relative to `metadata_modified` (not
    "now") — the gap gate compares the two directly.
    """
    analyzed_at = MODIFIED
    modified = analyzed_at + timedelta(days=updated_days_after_analysis)
    return SourceRecord(
        id=dataset_id,
        title="מאגר לדוגמה",
        metadata_modified=modified,
        analyzed_metadata_modified=analyzed_at,
        last_analyzed_at=analyzed_at,
        analysis_status="succeeded",
        change_status="updated",
    )


def test_track2_skips_update_soon_after_analysis():
    """Data updated 5 days after our build ⇒ page is still fresh enough;
    no rebuild (the gap gate, not a calendar cooldown, decides)."""
    src = _gap_src("small-gap", updated_days_after_analysis=5)
    assert pick_next(_store([src]), n=5) == []


def test_track2_picks_update_well_after_analysis():
    """Data moved on 40 days after our build ⇒ rebuild on the next run,
    regardless of how recently that update happened."""
    src = _gap_src("big-gap", updated_days_after_analysis=40)
    assert [s.id for s in pick_next(_store([src]), n=5)] == ["big-gap"]


def test_track2_gap_days_is_configurable():
    src = _gap_src("sixty-day-gap", updated_days_after_analysis=60)
    assert [s.id for s in pick_next(_store([src]), n=5)] == ["sixty-day-gap"]
    assert pick_next(_store([src]), n=5, reanalyze_gap_days=90) == []


# The `min_modified_floor` / `max_age_days` gates are env-driven (the
# pipeline reads MIN_MODIFIED_FLOOR / MAX_AGE_DAYS and passes them in).
# These lock in the floor: a 2025 never-analyzed source is eligible once
# the floor drops to 2025-01-01, while a 2024 one stays excluded. A large
# max_age_days disables the rolling window so the floor is the sole gate
# (otherwise now-365d would clip early-2025 too).
FLOOR_2025 = datetime(2025, 1, 1, tzinfo=timezone.utc)


def _never_src(dataset_id: str, metadata_modified: datetime) -> SourceRecord:
    return SourceRecord(
        id=dataset_id,
        title="מאגר חדש",
        metadata_modified=metadata_modified,
        analysis_status="never",
        change_status="new",
    )


def test_floor_admits_2025_source_when_lowered():
    src = _never_src("y2025", datetime(2025, 3, 1, tzinfo=timezone.utc))
    store = MagicMock()
    store.list_never_analyzed.return_value = [src]
    store.list_failed_retryable.return_value = []
    store.list_changed_sources.return_value = []
    picks = pick_next(
        store, n=5, min_modified_floor=FLOOR_2025, max_age_days=100000
    )
    assert [s.id for s in picks] == ["y2025"]


def test_floor_still_excludes_2024_source():
    src = _never_src("y2024", datetime(2024, 12, 1, tzinfo=timezone.utc))
    store = MagicMock()
    store.list_never_analyzed.return_value = [src]
    store.list_failed_retryable.return_value = []
    store.list_changed_sources.return_value = []
    picks = pick_next(
        store, n=5, min_modified_floor=FLOOR_2025, max_age_days=100000
    )
    assert picks == []
