"""Tests for the restricted-status lifecycle in FirestoreStateStore.

Mocks the firestore client (no emulator, matching the rest of the suite).
Covers the two halves of the 403-restriction feature:
  - mark_analysis_restricted parks a source WITHOUT bumping failed_attempts.
  - save_dataset resets a restricted doc back to `never` when the scanner sees
    the dataset again (re-enable on reappearance), but leaves other statuses
    untouched.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from services.scanner.models import Dataset
from services.shared.firestore import FirestoreStateStore


def _store_with_existing(existing: dict | None):
    store = FirestoreStateStore.__new__(FirestoreStateStore)
    client = MagicMock()
    snap = MagicMock()
    snap.exists = existing is not None
    snap.to_dict.return_value = existing or {}
    ref = MagicMock()
    ref.get.return_value = snap
    client.collection.return_value.document.return_value = ref
    store.client = client
    return store, ref


def _dataset() -> Dataset:
    return Dataset.from_ckan_response(
        {
            "id": "fa475dcc-5d80-41b0-af4c-142708bbc2bc",
            "name": "x",
            "title": "מאגר לדוגמה",
            "metadata_modified": "2026-05-01T00:00:00",
            "resources": [
                {
                    "id": "r1",
                    "name": "main",
                    "format": "csv",
                    "url": "https://data.gov.il/dataset/x/resource/r1/download/x.csv",
                }
            ],
        }
    )


def _payload(ref) -> dict:
    return ref.set.call_args[0][0]


def test_save_dataset_resets_restricted_to_never():
    store, ref = _store_with_existing({"analysis_status": "restricted"})
    store.save_dataset(_dataset(), change_status="updated")
    p = _payload(ref)
    assert p["analysis_status"] == "never"
    assert p["last_error"] is None
    assert p["failed_attempts"] == 0


def test_save_dataset_preserves_status_for_non_restricted_existing():
    store, ref = _store_with_existing({"analysis_status": "succeeded"})
    store.save_dataset(_dataset(), change_status="updated")
    # Existing-doc, non-restricted branch must not touch analyzer fields.
    assert "analysis_status" not in _payload(ref)


def test_save_dataset_new_doc_initializes_never():
    store, ref = _store_with_existing(None)
    store.save_dataset(_dataset(), change_status="new")
    p = _payload(ref)
    assert p["analysis_status"] == "never"
    assert p["first_seen_at"] is not None


def test_mark_analysis_restricted_sets_status_without_failed_attempts():
    store, ref = _store_with_existing({"analysis_status": "never"})
    store.mark_analysis_restricted("fa475dcc", "CKAN datastore 403 for resource r1")
    p = _payload(ref)
    assert p["analysis_status"] == "restricted"
    assert "403" in p["last_error"]
    # An exclusion, not a retryable failure — must NOT consume retry budget.
    assert "failed_attempts" not in p
