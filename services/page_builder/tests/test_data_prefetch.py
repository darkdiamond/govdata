"""Tests for the full-data prefetch (agent_contract.fetch_resource_records_to_file
/ prefetch_dataset), resource selection, and the user-message manifest.

The fetcher pages datastore_search host-side and streams one CSV per
resource; every failure/gate path must degrade to "no file" (a session
must never be blocked on prefetch). Over-cap resources fall back to a
deterministic sample when DATA_PREFETCH_SAMPLE_ROWS is set. The manifest
block only appears when at least one file was provisioned.
"""
from __future__ import annotations

import csv
import io
import json
import time
import urllib.error as urllib_error
from urllib.parse import parse_qs, urlparse

import pytest

from services.page_builder import agent_contract
from services.page_builder.agent_contract import (
    PrefetchedResource,
    build_user_message,
    fetch_resource_records_to_file,
    prefetch_dataset,
)
from services.shared.resources import select_prefetch_resources


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


def _fetch(dest, total, *, max_bytes=10_000_000, page_size=4, sample_rows=0,
           prefer_sample=False, resource_id="res-1"):
    return fetch_resource_records_to_file(
        resource_id,
        total,
        dest,
        max_bytes=max_bytes,
        page_size=page_size,
        page_timeout_s=5.0,
        deadline=time.monotonic() + 60,
        sample_target_rows=sample_rows,
        prefer_sample=prefer_sample,
    )


def test_full_export_pages_and_normalizes(monkeypatch, tmp_path):
    records = _make_records(10)
    calls = _paged_urlopen(monkeypatch, records, page_size_expected=4)
    dest = tmp_path / "data_1.csv"

    outcome = _fetch(dest, total=10)
    assert outcome is not None
    assert outcome.mode == "full"
    assert outcome.rows == 10
    assert calls == [0, 4, 8]

    rows = list(csv.DictReader(io.StringIO(dest.read_text(encoding="utf-8"))))
    assert len(rows) == 10
    # _id dropped, Hebrew fields preserved, None → empty string
    assert set(rows[0].keys()) == {"שם", "ערך"}
    assert rows[0]["שם"] == "רשומה 0"
    assert rows[0]["ערך"] == ""  # i=0 → None
    assert rows[1]["ערך"] == "1.5"
    assert outcome.bytes == dest.stat().st_size


def test_gates_return_none(monkeypatch, tmp_path):
    def boom(*_a, **_k):  # urlopen must not be reached when gated
        raise AssertionError("network touched despite gate")

    monkeypatch.setattr(agent_contract.urllib_request, "urlopen", boom)
    dest = tmp_path / "d.csv"
    assert _fetch(dest, total=10, resource_id="") is None
    assert _fetch(dest, total=0) is None
    assert _fetch(dest, total=10, max_bytes=0) is None
    # prefer_sample with sampling disabled: no full fetch, no sample → None
    assert _fetch(dest, total=10, prefer_sample=True, sample_rows=0) is None


def test_http_error_returns_none_and_removes_file(monkeypatch, tmp_path):
    def fake(req, timeout=None):  # noqa: ANN001
        raise urllib_error.HTTPError("http://x", 500, "err", None, io.BytesIO(b""))

    monkeypatch.setattr(agent_contract.urllib_request, "urlopen", fake)
    dest = tmp_path / "d.csv"
    assert _fetch(dest, total=10) is None
    assert not dest.exists()


def test_byte_cap_falls_back_to_sample(monkeypatch, tmp_path):
    records = _make_records(100)
    calls = _paged_urlopen(monkeypatch, records, page_size_expected=4)
    dest = tmp_path / "d.csv"

    # Cap far below the full CSV: full fetch aborts mid-stream, sample of
    # ~2 blocks (8 rows) fits.
    outcome = _fetch(dest, total=100, max_bytes=600, sample_rows=8)
    assert outcome is not None
    assert outcome.mode == "sample"
    assert outcome.rows == 8
    assert "blocks" in outcome.sample_note
    # Sample offsets restart from 0 with stride 50 after the aborted walk.
    assert calls[-2:] == [0, 50]


def test_byte_cap_without_sampling_returns_none(monkeypatch, tmp_path):
    _paged_urlopen(monkeypatch, _make_records(100), page_size_expected=4)
    dest = tmp_path / "d.csv"
    assert _fetch(dest, total=100, max_bytes=600, sample_rows=0) is None
    assert not dest.exists()


def test_sample_offsets_are_deterministic(monkeypatch, tmp_path):
    records = _make_records(100)
    calls = _paged_urlopen(monkeypatch, records, page_size_expected=4)
    dest = tmp_path / "d.csv"

    outcome = _fetch(dest, total=100, sample_rows=8, prefer_sample=True)
    assert outcome is not None
    assert outcome.mode == "sample"
    # ceil(8/4)=2 blocks, stride max(100//2, 4)=50 → offsets 0, 50
    assert calls == [0, 50]
    rows = list(csv.DictReader(io.StringIO(dest.read_text(encoding="utf-8"))))
    assert [r["שם"] for r in rows[:2]] == ["רשומה 0", "רשומה 1"]
    assert rows[4]["שם"] == "רשומה 50"


# ---- resource selection -------------------------------------------------


def _res(id, name, fmt, active=True):
    return {"id": id, "name": name, "format": fmt, "datastore_active": active}


def test_select_keeps_primary_first_and_dedupes_format_twins():
    resources = [
        _res("r-xlsx", "שמות רחובות XLSX", "XLSX"),
        _res("r-csv", "שמות רחובות csv", "CSV"),
        _res("r-other", "מדדים לפי שנה", "CSV"),
        _res("r-doc", "מילון נתונים", "PDF", active=False),
    ]
    picked = select_prefetch_resources(resources)
    # primary (CSV wins format priority) first; XLSX twin deduped; PDF dropped
    assert [r["id"] for r in picked] == ["r-csv", "r-other"]


def test_select_no_datastore_resources():
    assert select_prefetch_resources([_res("r1", "קובץ", "PDF", active=False)]) == []


def test_select_distinct_tables_survive():
    resources = [
        _res("r1", "סניפים 2023", "CSV"),
        _res("r2", "סניפים 2024", "CSV"),
        _res("r3", "סניפים 2025", "CSV"),
    ]
    assert len(select_prefetch_resources(resources)) == 3


# ---- prefetch_dataset ----------------------------------------------------


def _preview(total):
    return {
        "fields": [{"id": "שם", "type": "text"}],
        "total": total,
        "sample_rows": [{"שם": "אבגד"}],
    }


def test_prefetch_dataset_multi_resource_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv("DATA_PREFETCH_MULTI", raising=False)
    monkeypatch.setattr(
        agent_contract, "fetch_resource_preview", lambda rid: _preview(10)
    )
    fetched = []

    def fake_fetch(rid, total, dest, **kw):
        fetched.append(rid)
        dest.write_bytes(b"a,b\n1,2\n")
        return agent_contract.FetchOutcome(rows=1, bytes=8, mode="full")

    monkeypatch.setattr(agent_contract, "fetch_resource_records_to_file", fake_fetch)
    resources = [_res("r1", "טבלה א", "CSV"), _res("r2", "טבלה ב", "CSV")]

    # Default is now multi: every datastore-active resource is fetched.
    out = prefetch_dataset(resources, tmp_path)
    assert fetched == ["r1", "r2"]
    assert [o.sandbox_filename for o in out] == ["data_1.csv", "data_2.csv"]
    assert all(o.mode == "full" for o in out)

    # Opt out with DATA_PREFETCH_MULTI=false → primary resource only.
    fetched.clear()
    monkeypatch.setenv("DATA_PREFETCH_MULTI", "false")
    out = prefetch_dataset(resources, tmp_path)
    assert fetched == ["r1"]
    assert len(out) == 1 and out[0].sandbox_filename == "data_1.csv"


def test_prefetch_dataset_multi_with_budget(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_PREFETCH_MULTI", "true")
    monkeypatch.setenv("DATA_PREFETCH_TOTAL_BYTES", "10")
    monkeypatch.setattr(
        agent_contract, "fetch_resource_preview", lambda rid: _preview(10)
    )

    def fake_fetch(rid, total, dest, *, max_bytes, **kw):
        if max_bytes < 8:
            return None
        dest.write_bytes(b"a,b\n1,2\n")
        return agent_contract.FetchOutcome(rows=1, bytes=8, mode="full")

    monkeypatch.setattr(agent_contract, "fetch_resource_records_to_file", fake_fetch)
    out = prefetch_dataset(
        [_res("r1", "טבלה א", "CSV"), _res("r2", "טבלה ב", "CSV")], tmp_path
    )
    assert len(out) == 2
    assert out[0].mode == "full"
    # Second resource exceeded the remaining aggregate budget → unfetched,
    # but still listed (schema present).
    assert out[1].mode == "unfetched"
    assert out[1].schema is not None


def test_prefetch_dataset_restricted_secondary_skipped(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_PREFETCH_MULTI", "true")

    def preview(rid):
        if rid == "r2":
            raise agent_contract.ResourceRestrictedError("403")
        return _preview(5)

    monkeypatch.setattr(agent_contract, "fetch_resource_preview", preview)
    monkeypatch.setattr(
        agent_contract,
        "fetch_resource_records_to_file",
        lambda *a, **k: agent_contract.FetchOutcome(rows=1, bytes=8, mode="full"),
    )
    # fake fetch doesn't write the file; create it so host_path stat works
    (tmp_path / "data_1.csv").write_bytes(b"a\n1\n")
    out = prefetch_dataset(
        [_res("r1", "טבלה א", "CSV"), _res("r2", "טבלה ב", "CSV")], tmp_path
    )
    assert [p.resource_id for p in out] == ["r1"]


def test_prefetch_dataset_restricted_primary_raises(monkeypatch, tmp_path):
    def preview(rid):
        raise agent_contract.ResourceRestrictedError("403")

    monkeypatch.setattr(agent_contract, "fetch_resource_preview", preview)
    with pytest.raises(agent_contract.ResourceRestrictedError):
        prefetch_dataset([_res("r1", "טבלה", "CSV")], tmp_path)


def test_prefetch_dataset_kill_switch(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_PREFETCH_MAX_RECORDS", "0")
    monkeypatch.setattr(
        agent_contract, "fetch_resource_preview", lambda rid: _preview(10)
    )

    def boom(*_a, **_k):
        raise AssertionError("data fetch attempted despite kill switch")

    monkeypatch.setattr(agent_contract, "fetch_resource_records_to_file", boom)
    out = prefetch_dataset([_res("r1", "טבלה", "CSV")], tmp_path)
    assert len(out) == 1 and out[0].mode == "unfetched"


# ---- user message --------------------------------------------------------


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


def _pf(filename, mode, rows, total, name="טבלה", note=None, path=None):
    return PrefetchedResource(
        resource_id="res-1",
        name=name,
        format="CSV",
        total=total,
        schema={"fields": [{"id": "שם", "type": "text"}], "total": total,
                "sample_rows": []},
        sandbox_filename=filename,
        host_path=path,
        rows=rows,
        mode=mode,
        sample_note=note,
    )


def test_user_message_manifest_full(tmp_path):
    f = tmp_path / "data_1.csv"
    f.write_bytes(b"x\n")
    msg = _msg(
        prefetched=[_pf("data_1.csv", "full", 1500, 1500, path=f)],
        data_dir="/work/data",
    )
    assert "pre_fetched_files" in msg
    assert "/work/data/" in msg
    assert "FULL, 1,500 rows" in msg
    assert ", primary" in msg
    assert "do NOT" in msg and "re-download" in msg
    assert "per-file schemas" in msg


def test_user_message_manifest_sample_discloses_true_total(tmp_path):
    f = tmp_path / "data_1.csv"
    f.write_bytes(b"x\n")
    msg = _msg(
        prefetched=[
            _pf("data_1.csv", "sample", 150_000, 4_105_332, note="6 blocks", path=f)
        ],
        data_dir="/work/data",
    )
    assert "SAMPLE: 150,000 of 4,105,332 rows" in msg
    assert "TRUE total is 4,105,332" in msg
    assert "disclose the sampling in Hebrew" in msg


def test_user_message_lists_unprovisioned(tmp_path):
    f = tmp_path / "data_1.csv"
    f.write_bytes(b"x\n")
    msg = _msg(
        prefetched=[
            _pf("data_1.csv", "full", 10, 10, path=f),
            _pf(None, "unfetched", 0, 85_000_000, name="טבלת ענק"),
        ],
        data_dir="/work/data",
    )
    assert "NOT provisioned (85,000,000 rows)" in msg


def test_user_message_schema_only_falls_back_to_legacy_block():
    msg = _msg(prefetched=[_pf(None, "unfetched", 0, 10)])
    assert "pre_fetched_schema" in msg
    assert "pre_fetched_files" not in msg


def test_user_message_silent_without_prefetch():
    msg = _msg()
    assert "pre_fetched_files" not in msg
    assert "pre_fetched_schema" not in msg


def test_user_message_related_candidates_block():
    msg = _msg(
        related_candidates=[
            {"id": "abc-1", "title": "מאגר קרוב", "tags": ["בנקים", "אשראי"]},
            {"id": "abc-2", "title": "מאגר אחר", "tags": []},
        ]
    )
    assert "related_candidates" in msg
    assert 'abc-1 — "מאגר קרוב" [tags: בנקים, אשראי]' in msg
    assert 'abc-2 — "מאגר אחר"' in msg
    assert "do NOT query CKAN package_search" in msg
    assert "related_candidates" not in _msg()


def test_user_message_previous_failure_block():
    msg = _msg(previous_failure="host self-check failed (exit 5): NO-ICON-HEADER")
    assert "previous_attempt_failure" in msg
    assert "NO-ICON-HEADER" in msg
    assert "previous_attempt_failure" not in _msg()


def test_schemas_block_capped():
    wide_schema = {
        "fields": [{"id": f"עמודה_{i}", "type": "text"} for i in range(40)],
        "total": 10,
        "sample_rows": [
            {f"עמודה_{i}": "ערך ארוך מאוד " * 10 for i in range(40)}
            for _ in range(5)
        ],
    }
    files = []
    for n in range(1, 6):
        p = _pf(f"data_{n}.csv", "full", 10, 10)
        p.schema = json.loads(json.dumps(wide_schema))
        files.append(p)
    block = agent_contract._render_schemas_block(files)
    assert len(block.encode("utf-8")) <= agent_contract._SCHEMAS_BLOCK_CAP + 2048
    parsed = json.loads(block)
    for entry in parsed.values():  # fields+total always survive
        assert entry["fields"] and entry["total"] == 10
