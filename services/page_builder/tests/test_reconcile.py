"""Reconcile sweep: flips succeeded→unavailable on 403, unavailable→succeeded on alive."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from services.page_builder import reconcile
from services.shared.firestore import SourceRecord


def _src(sid: str, status: str, rid: str | None = "rid-1") -> SourceRecord:
    resources = [{"id": rid, "format": "CSV", "url": f"https://x/resource/{rid}/download/x.csv"}] if rid else []
    return SourceRecord(id=sid, title="t", analysis_status=status, resources=resources)


@pytest.mark.asyncio
async def test_marks_succeeded_source_unavailable_on_gone():
    store = MagicMock()
    store.iter_publishable_sources.return_value = iter([_src("a", "succeeded")])
    client = MagicMock()
    client.probe_resource = AsyncMock(return_value="gone")
    client.probe_package = AsyncMock(return_value="gone")

    summary = await reconcile.reconcile_sources(store, client)

    store.mark_source_unavailable.assert_called_once_with("a", "reconcile: datastore probe returned gone")
    store.clear_source_unavailable.assert_not_called()
    assert summary["marked_unavailable"] == ["a"]


@pytest.mark.asyncio
async def test_recovers_unavailable_source_on_alive():
    store = MagicMock()
    store.iter_publishable_sources.return_value = iter([_src("b", "unavailable")])
    client = MagicMock()
    client.probe_resource = AsyncMock(return_value="alive")
    client.probe_package = AsyncMock(return_value="alive")

    summary = await reconcile.reconcile_sources(store, client)

    store.clear_source_unavailable.assert_called_once_with("b")
    store.mark_source_unavailable.assert_not_called()
    assert summary["recovered"] == ["b"]


@pytest.mark.asyncio
async def test_unknown_probe_changes_nothing():
    store = MagicMock()
    store.iter_publishable_sources.return_value = iter([_src("c", "succeeded")])
    client = MagicMock()
    client.probe_resource = AsyncMock(return_value="unknown")
    client.probe_package = AsyncMock(return_value="unknown")

    summary = await reconcile.reconcile_sources(store, client)

    store.mark_source_unavailable.assert_not_called()
    store.clear_source_unavailable.assert_not_called()
    assert summary["checked"] == 1


@pytest.mark.asyncio
async def test_already_unavailable_and_still_gone_is_noop():
    store = MagicMock()
    store.iter_publishable_sources.return_value = iter([_src("d", "unavailable")])
    client = MagicMock()
    client.probe_resource = AsyncMock(return_value="gone")
    client.probe_package = AsyncMock(return_value="gone")

    await reconcile.reconcile_sources(store, client)

    store.mark_source_unavailable.assert_not_called()
    store.clear_source_unavailable.assert_not_called()


@pytest.mark.asyncio
async def test_no_primary_resource_falls_back_to_package_probe():
    store = MagicMock()
    store.iter_publishable_sources.return_value = iter([_src("e", "succeeded", rid=None)])
    client = MagicMock()
    client.probe_resource = AsyncMock(return_value="unknown")
    client.probe_package = AsyncMock(return_value="gone")

    await reconcile.reconcile_sources(store, client)

    client.probe_package.assert_awaited_once_with("e")
    store.mark_source_unavailable.assert_called_once()
