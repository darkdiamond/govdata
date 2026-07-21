"""Tests for CKANClient.probe_resource / probe_package tri-state."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from services.scanner.client import CKANClient


def _resp(*, status: int, body: dict | None = None) -> MagicMock:
    r = MagicMock(spec=httpx.Response)
    r.status_code = status
    r.json = MagicMock(return_value=body) if body is not None else MagicMock(side_effect=ValueError)
    return r


def _client(get_mock) -> CKANClient:
    c = CKANClient.__new__(CKANClient)
    c._client = MagicMock()
    c._client.get = get_mock
    c._last_request_time = 0
    from services.scanner.config import settings as cfg
    c.config = cfg
    return c


@pytest.mark.asyncio
async def test_resource_gone_on_403():
    c = _client(AsyncMock(return_value=_resp(status=403, body={"success": False})))
    assert await c.probe_resource("rid") == "gone"


@pytest.mark.asyncio
async def test_resource_alive_on_200_success():
    c = _client(AsyncMock(return_value=_resp(status=200, body={"success": True, "result": {"total": 5}})))
    assert await c.probe_resource("rid") == "alive"


@pytest.mark.asyncio
async def test_resource_unknown_on_404():
    c = _client(AsyncMock(return_value=_resp(status=404, body={"success": False})))
    assert await c.probe_resource("rid") == "unknown"


@pytest.mark.asyncio
async def test_resource_unknown_on_transport_error():
    c = _client(AsyncMock(side_effect=httpx.TimeoutException("t")))
    assert await c.probe_resource("rid") == "unknown"


@pytest.mark.asyncio
async def test_package_gone_on_403():
    c = _client(AsyncMock(return_value=_resp(status=403, body={"success": False})))
    assert await c.probe_package("pid") == "gone"


@pytest.mark.asyncio
async def test_package_alive_on_200_success():
    c = _client(AsyncMock(return_value=_resp(status=200, body={"success": True, "result": {"id": "pid"}})))
    assert await c.probe_package("pid") == "alive"
