"""Tests for services.scanner.models parsing of CKAN responses."""
from __future__ import annotations

from services.scanner.models import Dataset


def _ckan_package(resources: list[dict]) -> dict:
    return {
        "id": "abc-123",
        "name": "test-dataset",
        "title": "מאגר בדיקה",
        "resources": resources,
    }


def test_from_ckan_response_parses_datastore_active():
    ds = Dataset.from_ckan_response(_ckan_package([
        {
            "id": "rid-1",
            "name": "main",
            "format": "csv",
            "url": "https://data.gov.il/dataset/x/resource/rid-1/download/x.csv",
            "datastore_active": True,
        },
        {
            "id": "rid-2",
            "name": "pdf",
            "format": "pdf",
            "url": "https://data.gov.il/dataset/x/resource/rid-2/download/x.pdf",
            # key absent — must default to False, not crash
        },
    ]))
    by_id = {r.id: r for r in ds.resources}
    assert by_id["rid-1"].datastore_active is True
    assert by_id["rid-2"].datastore_active is False
