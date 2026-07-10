"""Tests for the full-data prefetch (agent_contract.fetch_resource_records)
and its user-message advertisement.

The fetcher pages datastore_search host-side and normalizes to one CSV;
every failure/gate path must return None (a session must never be blocked
on prefetch). The user-message block only appears when a data path is
passed.
"""
from __future__ import annotations

import csv
import io
import json
import urllib.error as urllib_error
from urllib.parse import parse_qs, urlparse

import pytest

from services.page_builder import agent_contract
from services.page_builder.agent_contract import (
    build_user_message,
    fetch_resource_records,
)


class _Resp:
    def __init__(self, body: bytes):
        self._body = body

    def __enter__(self) -> "_Resp":
        return self

    def __exit__(self, *_a) -> bool:
        return False

    def read(self) -> bytes:
        return self._body


_FIELDS = [{"id": "_id", "type": "int"}, {"id": "שם", "type": "text"}, {"id": "ערך", "type": "numeric"}]


def _paged_urlopen(monkeypatch, records: list[dict], page_size_expected: int):
    """Serve `records` through a fake datastore_search honoring offset/limit."""
    calls = []

    def fake(req, timeout=None):  # noqa: ANN001
        q = parse_qs(urlparse(req.full_url).query)
        offset = int(q.get("offset", ["0"])[0])
        limit = int(q["limit"][0])
        assert limit == page_size_expected
        calls.append(offset)
        body = {
            "success": True,
            "result": {"fields": _FIELDS, "records": records[offset : offset + limit]},
        }
        return _Resp(json.dumps(body, ensure_ascii=False).encode("utf-8"))

    monkeypatch.setattr(agent_contract.urllib_request, "urlopen", fake)
    return calls


def _make_records(n: int) -> list[dict]:
    return [{"_id": i + 1, "שם": f"רשומה {i}", "ערך": i * 1.5 if i % 3 else None} for i in range(n)]


def test_full_export_pages_and_normalizes(monkeypatch):
    monkeypatch.setattr(agent_contract, "_DATA_PREFETCH_PAGE_SIZE", 4)
    records = _make_records(10)
    calls = _paged_urlopen(monkeypatch, records, page_size_expected=4)

    data = fetch_resource_records("res-1", total=10, max_records=100)
    assert data is not None
    assert calls == [0, 4, 8]

    rows = list(csv.DictReader(io.StringIO(data.decode("utf-8"))))
    assert len(rows) == 10
    # _id dropped, Hebrew fields preserved, None → empty string
    assert set(rows[0].keys()) == {"שם", "ערך"}
    assert rows[0]["שם"] == "רשומה 0"
    assert rows[0]["ערך"] == ""  # i=0 → None
    assert rows[1]["ערך"] == "1.5"


def test_gates_return_none(monkeypatch):
    def boom(*_a, **_k):  # urlopen must not be reached when gated
        raise AssertionError("network touched despite gate")

    monkeypatch.setattr(agent_contract.urllib_request, "urlopen", boom)
    assert fetch_resource_records("", total=10, max_records=100) is None
    assert fetch_resource_records("res-1", total=0, max_records=100) is None
    assert fetch_resource_records("res-1", total=101, max_records=100) is None
    assert fetch_resource_records("res-1", total=10, max_records=0) is None


def test_env_gate(monkeypatch):
    monkeypatch.setenv("DATA_PREFETCH_MAX_RECORDS", "5")

    def boom(*_a, **_k):
        raise AssertionError("network touched despite env gate")

    monkeypatch.setattr(agent_contract.urllib_request, "urlopen", boom)
    assert fetch_resource_records("res-1", total=6) is None


def test_http_error_returns_none(monkeypatch):
    def fake(req, timeout=None):  # noqa: ANN001
        raise urllib_error.HTTPError("http://x", 500, "err", None, io.BytesIO(b""))

    monkeypatch.setattr(agent_contract.urllib_request, "urlopen", fake)
    assert fetch_resource_records("res-1", total=10, max_records=100) is None


def test_byte_cap_returns_none(monkeypatch):
    monkeypatch.setattr(agent_contract, "_DATA_PREFETCH_BYTE_CAP", 50)
    _paged_urlopen(monkeypatch, _make_records(10), page_size_expected=5000)
    assert fetch_resource_records("res-1", total=10, max_records=100) is None


def _msg(**kw) -> str:
    return build_user_message(
        dataset_id="d1",
        title="t",
        notes="n",
        org_title="o",
        primary_resource_id="res-1",
        outputs_dir="/out",
        check_script="/check.py",
        **kw,
    )


def test_user_message_advertises_data_file():
    msg = _msg(pre_fetched_data_path="/work/data.csv", pre_fetched_data_rows=1500)
    assert "pre_fetched_data" in msg
    assert "/work/data.csv" in msg
    assert "1,500" in msg
    assert "do NOT re-download" in msg


def test_user_message_silent_without_data():
    assert "pre_fetched_data:" not in _msg()
