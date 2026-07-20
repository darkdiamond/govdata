"""An `unavailable` source flagged `updated` must not be re-selected."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from services.page_builder import selector
from services.shared.firestore import SourceRecord


def test_unavailable_source_not_reselected_in_track2():
    old = datetime(2025, 6, 1, tzinfo=timezone.utc)          # built-from version
    newer = datetime(2026, 6, 1, tzinfo=timezone.utc)        # CKAN advanced, >30d gap
    src = SourceRecord(
        id="dead",
        title="t",
        analysis_status="unavailable",
        change_status="updated",
        metadata_modified=newer,
        analyzed_metadata_modified=old,
        last_analyzed_at=old,
    )
    store = MagicMock()
    store.list_never_analyzed.return_value = []
    store.list_failed_retryable.return_value = []
    store.list_changed_sources.return_value = [src]

    picks = selector.pick_next(
        store, n=5, reanalyze=True,
        min_modified_floor=datetime(2025, 1, 1, tzinfo=timezone.utc),
        max_age_days=100000,
    )
    assert picks == []
