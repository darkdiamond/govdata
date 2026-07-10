"""Cost telemetry: per-response billed-cost assembly + fallbacks.

The goal is that `last_usage.actual_cost_usd` matches what the OpenRouter
dashboard bills: inline `usage.cost` per response when present, the
`/api/v1/generation` endpoint for the intermittent responses that arrive
without it, and a cache-aware price-table estimate as the last resort.

Run: pytest services/page_builder/tests/test_cost.py
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import pytest

from services.page_builder import model_harness as mh


# ---------------------------------------------------------------- fakes

@dataclass
class FakeResponse:
    """Duck-typed pydantic_ai ModelResponse."""
    kind: str = "response"
    provider_details: Optional[dict] = None
    provider_response_id: Optional[str] = None
    usage: Optional[dict] = None


@dataclass
class FakeRequest:
    kind: str = "request"


def _run_usage(**over) -> dict[str, int]:
    base = {"input_tokens": 1000, "output_tokens": 100, "total_tokens": 1100,
            "cache_read_tokens": 0, "cache_write_tokens": 0}
    base.update(over)
    return base


# ---------------------------------------------------------- _extract_usage

def test_extract_usage_reads_top_level_cache_tokens():
    # PydanticAI RunUsage exposes cache counts as top-level fields.
    u = mh._extract_usage({
        "input_tokens": 1000, "output_tokens": 100,
        "cache_read_tokens": 800, "cache_write_tokens": 50,
    })
    assert u["cache_read_tokens"] == 800
    assert u["cache_write_tokens"] == 50


def test_extract_usage_details_fallback_still_works():
    u = mh._extract_usage({
        "input_tokens": 1000, "output_tokens": 100,
        "details": {"cached_tokens": 700, "cache_creation_input_tokens": 30},
    })
    assert u["cache_read_tokens"] == 700
    assert u["cache_write_tokens"] == 30


# ---------------------------------------------------------- _compute_cost

MODEL = "minimax/minimax-m3"  # in PRICE_TABLE: input .30 / cached .06 / output 1.20


def test_all_inline_costs_sum_to_openrouter_source(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    messages = [
        FakeRequest(),
        FakeResponse(provider_details={"cost": 0.01}),
        FakeRequest(),
        FakeResponse(provider_details={"cost": 0.02}),
        FakeResponse(provider_details={"cost": 0.005}),
    ]
    cost = mh._compute_cost(model=MODEL, usage=_run_usage(), messages=messages)
    assert cost["total_usd"] == pytest.approx(0.035)
    assert cost["cost_source"] == "openrouter"
    assert cost["breakdown"] == {"responses": 3, "inline": 2 + 1, "fetched": 0,
                                 "estimated": 0}


def test_byok_inline_cost_uses_upstream_inference_cost(monkeypatch):
    # With BYOK (our MiniMax setup), OpenRouter credits are ~0 and the
    # real spend is what the upstream provider bills. Verified live
    # 2026-07-10: usage.cost == 0, cost_details.upstream_inference_cost
    # carries the actual USD.
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    messages = [
        FakeResponse(provider_details={
            "cost": 0, "upstream_inference_cost": 3.684e-05, "is_byok": True,
        }),
        FakeResponse(provider_details={
            "cost": 0, "upstream_inference_cost": 5.0e-05, "is_byok": True,
        }),
    ]
    cost = mh._compute_cost(model=MODEL, usage=_run_usage(), messages=messages)
    assert cost["total_usd"] == pytest.approx(8.684e-05, abs=1e-6)
    assert cost["cost_source"] == "openrouter"
    assert cost["breakdown"]["inline"] == 2


def test_missing_inline_cost_fetched_from_generation_api(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    fetched_ids: list[str] = []

    def fake_fetch(gen_id: str, api_key: str, **kw) -> Optional[float]:
        fetched_ids.append(gen_id)
        assert api_key == "k"
        return 0.004

    monkeypatch.setattr(mh, "_fetch_generation_cost", fake_fetch)
    messages = [
        FakeResponse(provider_details={"cost": 0.01},
                     provider_response_id="gen-a"),
        FakeResponse(provider_details={}, provider_response_id="gen-b"),
    ]
    cost = mh._compute_cost(model=MODEL, usage=_run_usage(), messages=messages)
    assert fetched_ids == ["gen-b"]  # only the response missing inline cost
    assert cost["total_usd"] == pytest.approx(0.014)
    assert cost["cost_source"] == "openrouter+api"
    assert cost["breakdown"] == {"responses": 2, "inline": 1, "fetched": 1,
                                 "estimated": 0}


def test_fetch_failure_falls_back_to_cache_aware_estimate(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setattr(mh, "_fetch_generation_cost", lambda *a, **k: None)
    messages = [
        FakeResponse(provider_details={"cost": 0.01}),
        FakeResponse(
            provider_response_id="gen-x",
            usage={"input_tokens": 100, "output_tokens": 10,
                   "cache_read_tokens": 80},
        ),
    ]
    cost = mh._compute_cost(model=MODEL, usage=_run_usage(), messages=messages)
    # estimate: 20 uncached * .30 + 80 cached * .06 + 10 out * 1.20 per 1M
    est = (20 * 0.30 + 80 * 0.06 + 10 * 1.20) / 1_000_000
    # totals are rounded to 6 decimals (USD micro-precision)
    assert cost["total_usd"] == pytest.approx(0.01 + est, abs=1e-6)
    assert cost["cost_source"] == "openrouter+estimate"
    assert cost["breakdown"]["estimated"] == 1


def test_nothing_inline_or_fetched_is_price_table(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    messages = [
        FakeResponse(usage={"input_tokens": 1000, "output_tokens": 100,
                            "cache_read_tokens": 800}),
    ]
    cost = mh._compute_cost(model=MODEL, usage=_run_usage(), messages=messages)
    est = (200 * 0.30 + 800 * 0.06 + 100 * 1.20) / 1_000_000
    assert cost["total_usd"] == pytest.approx(est)
    assert cost["cost_source"] == "price_table"


def test_unknown_model_with_no_cost_data_returns_none():
    messages = [FakeResponse(usage={"input_tokens": 10, "output_tokens": 1})]
    cost = mh._compute_cost(model="someone/mystery-model",
                            usage=_run_usage(), messages=messages)
    assert cost["total_usd"] is None
    assert cost["cost_source"] is None


# ------------------------------------------------- _fetch_generation_cost

class _FakeHTTPResponse:
    def __init__(self, status_code: int, payload: Optional[dict] = None):
        self.status_code = status_code
        self._payload = payload or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def test_fetch_generation_cost_parses_total_cost(monkeypatch):
    calls: list[dict[str, Any]] = []

    def fake_get(url, **kw):
        calls.append({"url": url, **kw})
        return _FakeHTTPResponse(200, {"data": {"total_cost": 0.0123}})

    monkeypatch.setattr(mh.httpx, "get", fake_get)
    assert mh._fetch_generation_cost("gen-1", "key") == pytest.approx(0.0123)
    assert calls[0]["params"] == {"id": "gen-1"}
    assert calls[0]["headers"]["Authorization"] == "Bearer key"


def test_fetch_generation_cost_sums_byok_upstream(monkeypatch):
    # BYOK: total_cost is the OpenRouter credits (~0), the real spend is
    # upstream_inference_cost. Live record 2026-07-10 had exactly this shape.
    payload = {"data": {"total_cost": 0, "upstream_inference_cost": 3.684e-05,
                        "cache_discount": 2.736e-05, "is_byok": True}}
    monkeypatch.setattr(mh.httpx, "get",
                        lambda *a, **k: _FakeHTTPResponse(200, payload))
    assert mh._fetch_generation_cost("gen-b", "key") == pytest.approx(3.684e-05)


def test_fetch_generation_cost_retries_on_lag_then_gives_up(monkeypatch):
    # Stats lag the response: observed live both as 404 and as HTTP 200
    # with total_cost still null ~2s after completion.
    seq = [
        _FakeHTTPResponse(404),
        _FakeHTTPResponse(200, {"data": {"total_cost": None}}),
        _FakeHTTPResponse(200, {"data": {"total_cost": 0.5}}),
    ]
    monkeypatch.setattr(mh.httpx, "get", lambda *a, **k: seq.pop(0))
    monkeypatch.setattr(mh.time, "sleep", lambda s: None)
    assert mh._fetch_generation_cost("gen-2", "key") == pytest.approx(0.5)

    monkeypatch.setattr(mh.httpx, "get", lambda *a, **k: _FakeHTTPResponse(404))
    assert mh._fetch_generation_cost("gen-3", "key") is None


# ------------------------------------------- attempt-cost accumulation

def test_failed_attempt_cost_lands_in_attempts_cost_usd(monkeypatch, tmp_path):
    from services.page_builder import agent_runner as ar
    from services.page_builder.model_harness import AgentSessionOutput

    def _out(cost_usd: float, agent_data_raw: bytes) -> AgentSessionOutput:
        return AgentSessionOutput(
            content_html_raw="<section>ok</section>",
            agent_data_raw=agent_data_raw,
            usage=_run_usage(cache_read_tokens=800, cache_write_tokens=10),
            cost={"tokens_usd": cost_usd, "total_usd": cost_usd,
                  "cost_source": "openrouter",
                  "breakdown": {"responses": 1, "inline": 1, "fetched": 0,
                                "estimated": 0}},
            iterations=3,
            tool_calls={},
            messages=[],
            elapsed_seconds=1.0,
        )

    outputs = [
        _out(0.02, b"not-valid-json"),  # attempt 1: fails AgentData validation
        _out(0.03, b'{"summary_he": "x", "dataset_kind": "misc"}'),
    ]
    monkeypatch.setattr(ar, "run_agent_session",
                        lambda **kw: outputs.pop(0))

    class FakeSandbox:
        def kill(self):
            pass

    monkeypatch.setattr(ar.LocalSandbox, "create",
                        staticmethod(lambda workdir: FakeSandbox()))
    monkeypatch.setattr(ar, "sanitize_content_html",
                        lambda html, dataset_id: html)
    monkeypatch.setattr(ar, "run_host_check", lambda *a, **k: None)
    monkeypatch.setattr(ar, "_write_gcs", lambda *a, **k: "gs://b/x")
    monkeypatch.setattr(ar, "SESSIONS_ROOT", tmp_path)

    captured: dict[str, Any] = {}

    class FakeStore:
        def set_agent_data(self, dataset_id, data):
            captured["agent_data"] = data

        def set_session_usage(self, dataset_id, *, usage, **kw):
            captured["usage"] = usage
            captured["kw"] = kw

    result = ar.run_production_session(
        dataset_id="ds-1", title="t", notes="n", org_title="o",
        gcs_bucket="bucket", store=FakeStore(), model=MODEL,
    )
    assert result.attempts == 2
    u = captured["usage"]
    # successful-session cost keeps its meaning; all-attempt spend is new
    assert u["actual_cost_usd"] == pytest.approx(0.03)
    assert u["attempts_cost_usd"] == pytest.approx(0.05)
    assert u["cache_write_tokens"] == 10
    assert u["cost_breakdown"] == {"responses": 1, "inline": 1, "fetched": 0,
                                   "estimated": 0}
