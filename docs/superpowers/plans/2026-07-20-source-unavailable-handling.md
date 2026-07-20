# Graceful Handling of Datasets Removed From Source — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a dataset is made private/removed at data.gov.il after we published its page, keep serving the last static snapshot and clearly flag the source as gone — instead of the explorer silently vanishing.

**Architecture:** Phase 1 is a self-contained frontend fix: the data explorer distinguishes a 403 from other failures and renders a "source gone" state instead of collapsing. Phase 2 adds an authoritative backend flag: a weekly reconcile sweep probes already-published sources, marks removed ones `unavailable` (page preserved, not dropped), the publisher stamps the flag into `data.json`/manifest, and the frontend renders an SSG banner + a listing badge.

**Tech Stack:** Python 3 (pydantic v2, google-cloud-firestore, httpx, tenacity, pytest/pytest-asyncio) for services; Nuxt 3 / Vue 3 (`<script setup>`, TypeScript) for the frontend.

## Global Constraints

- **Spec:** `docs/superpowers/specs/2026-07-20-source-unavailable-handling-design.md`.
- **Hebrew-first, RTL.** All user-facing copy is Hebrew; the explorer component is `dir="rtl"`.
- **`content.html` is retained forever — no expiry.** Never add a GCS lifecycle rule; the publisher rsync already keeps `content.html`. Hard requirement.
- **Two new `analysis_status` values coexist:** keep existing `restricted` (never-succeeded 403 → no page, current behaviour) unchanged; add `unavailable` (previously-succeeded then gone → page preserved).
- **Self-heal flips `unavailable`→`succeeded`, never `→never`** (never would drop the page from the publisher until re-analysis).
- **No frontend test runner exists** (no vitest/jest in `frontend/package.json`). Frontend tasks are verified by `npx nuxi typecheck` plus manual driving; do NOT scaffold a test framework.
- **Python tests** live in `services/<svc>/tests/`, run with `pytest`, and mock Firestore/httpx (never hit the network). Follow the existing patterns in `test_publish.py` and `test_datastore_total.py`.
- **Reconcile defaults:** env knob `RECONCILE_ENABLED` (default `false`), `RECONCILE_WEEKDAY` (default `6` = Sunday, Python `datetime.weekday()`), timezone Asia/Jerusalem.
- **Probe tri-state:** `"gone"` (HTTP 403), `"alive"` (HTTP 2xx + `success:true`), `"unknown"` (anything else — never flips a flag).
- Activate the venv first: `source .venv/bin/activate`.

---

# PHASE 1 — Explorer stops vanishing (frontend only, ships independently)

### Task 1: DatasetExplorer renders a "source gone" state on 403

**Files:**
- Modify: `frontend/components/DatasetExplorer.vue`

**Interfaces:**
- Consumes: nothing new.
- Produces: internal only — a `sourceGone` ref and an `isGoneError()` helper. No prop/emit changes (Phase 2 adds the prop). The component's public props stay `{ resources, primaryResourceId, recordCount }`.

**Behaviour contract:**
- Schema probe (`loadSchema`) or page load (`loadPage`) receiving **HTTP 403** → set `sourceGone = true`, keep the `<section>` visible, render the gone-state (no search, no table, no pagination, **no download link**).
- **404 / `success:false` / not-datastore-backed** → unchanged (collapses the section).
- **Transient failure after schema loaded** → unchanged (`fetchError` red state, with its download link).

- [ ] **Step 1: Make `dsSearch` carry the HTTP status on the thrown error**

In `frontend/components/DatasetExplorer.vue`, in `dsSearch()`, replace:

```ts
  const res = await fetch(`${API}?${params}`, { signal })
  if (!res.ok) throw new Error(`http ${res.status}`)
```

with:

```ts
  const res = await fetch(`${API}?${params}`, { signal })
  if (!res.ok) {
    const err = new Error(`http ${res.status}`) as Error & { status?: number }
    err.status = res.status
    throw err
  }
```

- [ ] **Step 2: Add the `sourceGone` ref and an `isGoneError` helper**

Next to the other refs (after `const fetchError = ref(false)` near line 102) add:

```ts
// Source made private / removed upstream: the live datastore_search returns
// HTTP 403 ("Authorization Error"). Distinct from a resource that was never
// datastore-backed (404 / success:false) — that still collapses the section.
const sourceGone = ref(false)

function isGoneError(err: unknown): boolean {
  return (
    typeof err === 'object' &&
    err !== null &&
    (err as { status?: number }).status === 403
  )
}
```

- [ ] **Step 3: Flag 403 in `loadSchema` (don't treat it as "drop")**

In `loadSchema()`, replace the bare catch:

```ts
  } catch {
    return null
  }
```

with:

```ts
  } catch (err) {
    if (isGoneError(err)) sourceGone.value = true
    return null
  }
```

- [ ] **Step 4: Keep the section on a gone-source in `activate`**

In `activate()`, the `if (!sch)` block currently drops the rid and collapses. Add a gone check at its top so a 403 keeps the section visible:

```ts
  if (!sch) {
    if (sourceGone.value) {
      // Access revoked upstream (403). Keep the section; the template
      // renders the gone-state instead of the table.
      loading.value = false
      return
    }
    // Resource isn't datastore-backed (or the datastore was dropped since
    // the scan). Unverified single candidate → the whole section goes;
    // verified candidate with siblings → drop just this tab.
    droppedRids.value = new Set([...droppedRids.value, rid])
    const next = visibleCandidates.value[0]
    if (next) void activate(next.rid)
    else collapsed.value = true
    return
  }
```

- [ ] **Step 5: Flag 403 in `loadPage` too (source dies mid-session / schema cached)**

In `loadPage()`, replace the catch:

```ts
  } catch (err) {
    if (seq !== reqSeq || (err instanceof DOMException && err.name === 'AbortError')) return
    rows.value = []
    total.value = 0
    fetchError.value = true
    loading.value = false
  }
```

with:

```ts
  } catch (err) {
    if (seq !== reqSeq || (err instanceof DOMException && err.name === 'AbortError')) return
    if (isGoneError(err)) {
      sourceGone.value = true
      rows.value = []
      total.value = 0
      loading.value = false
      return
    }
    rows.value = []
    total.value = 0
    fetchError.value = true
    loading.value = false
  }
```

- [ ] **Step 6: Render the gone-state; hide everything else when gone**

In the `<template>`, the section currently is:

```html
    <div class="flex items-center gap-2 mb-3">
      <img src="/icons/database.svg" alt="" class="w-5 h-5" />
      <h2 class="m-0 text-lg font-semibold text-ink-deep">עיון בנתונים</h2>
    </div>

    <div v-if="visibleCandidates.length > 1" ... >
      ... resource pills ...
    </div>

    <template v-if="!schemaEmpty">
      ... search input + hint ...
    </template>
    ... schemaEmpty state / table wrap / legend / col-note / pagination ...
```

Wrap **everything after the header `<div>`** in a `sourceGone` branch. Insert immediately after the header div's closing `</div>`:

```html
    <div v-if="sourceGone" class="explorer-state explorer-state--error">
      מאגר זה אינו זמין עוד במקור הנתונים (data.gov.il). הנתונים המוצגים בעמוד הם תמונת מצב מהסריקה האחרונה שלנו.
    </div>

    <template v-else>
```

and add the matching `</template>` immediately before the section's closing `</section>` (after the pagination `<div>`). The gone-state deliberately has **no** download link. All existing inner blocks (pills, search, `schemaEmpty` state, table wrap, legend, column-count note, pagination) now live under the `v-else`.

- [ ] **Step 7: Typecheck**

Run: `cd frontend && npx nuxi typecheck`
Expected: no new type errors from `DatasetExplorer.vue`.

- [ ] **Step 8: Manual drive against a real dead + a real live dataset**

The 403 comes from live data.gov.il, so verify end-to-end. Ensure the two datasets' `data.json` exist locally (run a publish from prod Firestore if needed, or copy from the live site), then:

Run: `cd frontend && npm run dev`
Then drive with the Playwright MCP browser (or a manual browser):
1. Navigate to the **dead** dataset (`a698417e`, slug `רשימת-לשכות-פרטיות-מורשות-לתיווך-עבודה-עובדים-ישראלים-בלבד-a698417e`). Confirm: the "עיון בנתונים" section is **present** and shows the gone-state text; **no** table, search box, or download link.
2. Navigate to the **live** dataset (`90b08091`). Confirm: the table loads normally with rows (no regression).

- [ ] **Step 9: Commit**

```bash
git add frontend/components/DatasetExplorer.vue
git commit -m "fix(explorer): show 'source gone' state on 403 instead of collapsing

When a dataset is made private/removed upstream, datastore_search 403s.
The schema probe used to treat that identically to 'not datastore-backed'
and silently remove the whole explorer. Now a 403 sets sourceGone and the
section stays visible with a clear notice; no dead download link."
```

---

# PHASE 2 — Authoritative flag + banner + listing badge (backend + frontend)

### Task 2: Add `source_status` + `unavailable_since` to the schemas

**Files:**
- Modify: `services/page_builder/schema.py` (`DatasetMeta`, `ManifestEntry`)
- Modify: `frontend/types/manifest.ts` (`DatasetMeta`, `ManifestEntry`, `SlimEntry`)
- Modify: `services/page_builder/publish.py` (`_SEARCH_INDEX_FIELDS`)
- Test: `services/page_builder/tests/test_source_status_schema.py`

**Interfaces:**
- Produces: `DatasetMeta.source_status: str = "available"`, `DatasetMeta.unavailable_since: Optional[datetime] = None` (same two fields on `ManifestEntry`). TS: `source_status?: string`, `unavailable_since?: string` on all three interfaces.

- [ ] **Step 1: Write the failing test**

Create `services/page_builder/tests/test_source_status_schema.py`:

```python
"""DatasetMeta/ManifestEntry carry the source-availability flag."""
from __future__ import annotations

from datetime import datetime, timezone

from services.page_builder.schema import DatasetMeta, ManifestEntry


def test_dataset_meta_defaults_available():
    m = DatasetMeta(id="x", slug="x", title="t")
    assert m.source_status == "available"
    assert m.unavailable_since is None


def test_dataset_meta_accepts_unavailable():
    ts = datetime(2026, 7, 20, tzinfo=timezone.utc)
    m = DatasetMeta(
        id="x", slug="x", title="t",
        source_status="unavailable", unavailable_since=ts,
    )
    assert m.source_status == "unavailable"
    assert m.unavailable_since == ts


def test_manifest_entry_has_source_status():
    e = ManifestEntry(id="x", slug="x", title="t", source_status="unavailable")
    assert e.source_status == "unavailable"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest services/page_builder/tests/test_source_status_schema.py -v`
Expected: FAIL — `DatasetMeta` has no `source_status` (extra ignored → attribute missing / default absent).

- [ ] **Step 3: Add the fields to `DatasetMeta`**

In `services/page_builder/schema.py`, in `DatasetMeta`, immediately before `version: int = 1` (line ~94) add:

```python
    # Availability of the upstream source at data.gov.il. "available" (the
    # default) or "unavailable" — set by the weekly reconcile sweep when a
    # previously-published dataset is made private/removed upstream. The page
    # is preserved (this snapshot); the frontend renders an archive banner
    # and the explorer its gone-state.
    source_status: str = "available"
    # UTC timestamp when the source was first detected as unavailable.
    unavailable_since: Optional[datetime] = None
```

- [ ] **Step 4: Add the fields to `ManifestEntry`**

In the same file, in `ManifestEntry`, before its `version: int = 1` add the same two lines:

```python
    source_status: str = "available"
    unavailable_since: Optional[datetime] = None
```

- [ ] **Step 5: Mirror the fields in TypeScript**

In `frontend/types/manifest.ts`, add to the `DatasetMeta` interface, the `ManifestEntry` interface, and the `SlimEntry` interface (each) these two optional fields:

```ts
  source_status?: string
  unavailable_since?: string
```

- [ ] **Step 6: Add the fields to the search-index projection**

In `services/page_builder/publish.py`, in `_SEARCH_INDEX_FIELDS`, add two entries so the listing badge has the data:

```python
    "last_analyzed_at",
    "source_status",
    "unavailable_since",
}
```

- [ ] **Step 7: Run test to verify it passes**

Run: `pytest services/page_builder/tests/test_source_status_schema.py -v`
Expected: PASS (3 tests).

- [ ] **Step 8: Typecheck frontend + run full publish tests (no regression)**

Run: `cd frontend && npx nuxi typecheck` — expected: clean.
Run: `pytest services/page_builder/tests/test_publish.py -v` — expected: still PASS.

- [ ] **Step 9: Commit**

```bash
git add services/page_builder/schema.py frontend/types/manifest.ts services/page_builder/publish.py services/page_builder/tests/test_source_status_schema.py
git commit -m "feat(schema): add source_status + unavailable_since to dataset meta"
```

---

### Task 3: Firestore helpers — mark/clear unavailable + publishable iterator

**Files:**
- Modify: `services/shared/firestore.py` (`SourceRecord`, `FirestoreStateStore`)
- Test: `services/page_builder/tests/test_source_unavailable_store.py`

**Interfaces:**
- Consumes: `Task 2` (`unavailable` status value semantics).
- Produces:
  - `SourceRecord.unavailable_since: Optional[datetime] = None`.
  - `FirestoreStateStore.mark_source_unavailable(dataset_id: str, error: str) -> None`
  - `FirestoreStateStore.clear_source_unavailable(dataset_id: str) -> None`
  - `FirestoreStateStore.iter_publishable_sources() -> Iterator[SourceRecord]` (yields `succeeded` ∪ `unavailable`).

- [ ] **Step 1: Write the failing test**

Create `services/page_builder/tests/test_source_unavailable_store.py`:

```python
"""FirestoreStateStore.mark/clear_source_unavailable payloads + SourceRecord."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from google.cloud import firestore

from services.shared.firestore import FirestoreStateStore, SourceRecord


def _store_with_existing(existing: dict) -> tuple[FirestoreStateStore, MagicMock]:
    client = MagicMock()
    doc_ref = client.collection.return_value.document.return_value
    snap = MagicMock()
    snap.exists = bool(existing)
    snap.to_dict.return_value = existing
    doc_ref.get.return_value = snap
    store = FirestoreStateStore(client=client)
    return store, doc_ref


def test_mark_unavailable_stamps_since_when_absent():
    store, doc_ref = _store_with_existing({})
    store.mark_source_unavailable("id1", "403 gone")
    payload = doc_ref.set.call_args.args[0]
    assert payload["analysis_status"] == "unavailable"
    assert payload["last_error"] == "403 gone"
    assert isinstance(payload["unavailable_since"], datetime)


def test_mark_unavailable_preserves_existing_since():
    ts = datetime(2026, 7, 1, tzinfo=timezone.utc)
    store, doc_ref = _store_with_existing({"unavailable_since": ts})
    store.mark_source_unavailable("id1", "still gone")
    payload = doc_ref.set.call_args.args[0]
    assert "unavailable_since" not in payload  # not re-stamped


def test_clear_unavailable_restores_succeeded_and_deletes_since():
    store, doc_ref = _store_with_existing({"analysis_status": "unavailable"})
    store.clear_source_unavailable("id1")
    payload = doc_ref.set.call_args.args[0]
    assert payload["analysis_status"] == "succeeded"
    assert payload["unavailable_since"] is firestore.DELETE_FIELD


def test_source_record_reads_unavailable_since():
    ts = datetime(2026, 7, 20, tzinfo=timezone.utc)
    doc = MagicMock()
    doc.id = "id1"
    doc.to_dict.return_value = {"analysis_status": "unavailable", "unavailable_since": ts}
    rec = SourceRecord.from_doc(doc)
    assert rec.unavailable_since == ts
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest services/page_builder/tests/test_source_unavailable_store.py -v`
Expected: FAIL — methods/attribute don't exist.

- [ ] **Step 3: Add `unavailable_since` to `SourceRecord`**

In `services/shared/firestore.py`, in the `SourceRecord` dataclass, after `last_error: Optional[str] = None` (line ~67) add:

```python
    # UTC timestamp the reconcile sweep first flagged the source as removed
    # upstream. Set by mark_source_unavailable, cleared by
    # clear_source_unavailable. None while the source is available.
    unavailable_since: Optional[datetime] = None
```

And in `SourceRecord.from_doc`, after `last_error=data.get("last_error"),` add:

```python
            unavailable_since=data.get("unavailable_since"),
```

- [ ] **Step 4: Add the mark/clear/iterate methods**

In `services/shared/firestore.py`, immediately after `mark_analysis_restricted` (ends ~line 507) add:

```python
    def mark_source_unavailable(self, dataset_id: str, error: str) -> None:
        """Flag a *previously-succeeded* source as removed upstream.

        Unlike `mark_analysis_restricted` (never-succeeded 403 → page
        dropped), this PRESERVES the page: the publisher still emits it
        (see `iter_publishable_sources`) with an archive banner. Stamps
        `unavailable_since` only on the first transition so the displayed
        date is the true first-detection time. Does not bump
        `failed_attempts`.
        """
        ref = self.client.collection(SOURCES_COLL).document(dataset_id)
        snap = ref.get()
        already = (snap.to_dict() or {}).get("unavailable_since") if snap.exists else None
        payload: dict = {
            "analysis_status": "unavailable",
            "last_error": (error or "")[:1000],
        }
        if not already:
            payload["unavailable_since"] = datetime.now(timezone.utc)
        ref.set(payload, merge=True)

    def clear_source_unavailable(self, dataset_id: str) -> None:
        """Self-heal: the source is reachable again. Flip back to
        `succeeded` (NOT `never` — that would drop the live page until a
        fresh agent run) and clear `unavailable_since`. Any genuine data
        change while it was gone is picked up by normal Track-2
        re-analysis once CKAN's metadata_modified advances.
        """
        self.client.collection(SOURCES_COLL).document(dataset_id).set(
            {
                "analysis_status": "succeeded",
                "unavailable_since": firestore.DELETE_FIELD,
                "last_error": None,
            },
            merge=True,
        )

    def iter_publishable_sources(self) -> Iterator[SourceRecord]:
        """Sources the publisher should emit: succeeded + unavailable.

        `unavailable` docs keep their frozen snapshot (content.html in GCS,
        scanner facts + agent_data in the doc) so the page is preserved with
        an archive banner.
        """
        query = self.client.collection(SOURCES_COLL).where(
            filter=FieldFilter("analysis_status", "in", ["succeeded", "unavailable"])
        )
        for d in query.stream():
            yield SourceRecord.from_doc(d)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest services/page_builder/tests/test_source_unavailable_store.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add services/shared/firestore.py services/page_builder/tests/test_source_unavailable_store.py
git commit -m "feat(firestore): mark/clear source unavailable + publishable iterator"
```

---

### Task 4: CKAN client — tri-state availability probe

**Files:**
- Modify: `services/scanner/client.py` (`CKANClient`)
- Test: `services/scanner/tests/test_probe_availability.py`

**Interfaces:**
- Produces:
  - `CKANClient.probe_resource(resource_id: str) -> str` → `"gone"|"alive"|"unknown"`
  - `CKANClient.probe_package(package_id: str) -> str` → `"gone"|"alive"|"unknown"`

- [ ] **Step 1: Write the failing test**

Create `services/scanner/tests/test_probe_availability.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest services/scanner/tests/test_probe_availability.py -v`
Expected: FAIL — `probe_resource` / `probe_package` not defined.

- [ ] **Step 3: Implement the probes**

In `services/scanner/client.py`, add these methods to `CKANClient` (e.g. after `datastore_total`, ~line 228):

```python
    async def _probe(self, url: str, params: dict) -> str:
        """Shared tri-state probe. 403 → "gone", 2xx+success → "alive",
        anything else (404, 5xx, success:false, parse/transport error) →
        "unknown" (caller leaves the flag unchanged)."""
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context.")
        await self._rate_limit()
        try:
            response = await self._client.get(url, params=params)
        except (httpx.HTTPError, httpx.TimeoutException):
            return "unknown"
        if response.status_code == 403:
            return "gone"
        if response.status_code >= 400:
            return "unknown"
        try:
            data = response.json()
        except ValueError:
            return "unknown"
        return "alive" if data.get("success") else "unknown"

    async def probe_resource(self, resource_id: str) -> str:
        """Is a datastore resource still readable? Uses a limit=0 probe."""
        return await self._probe(
            self.config.datastore_search_url,
            {"resource_id": resource_id, "limit": 0},
        )

    async def probe_package(self, package_id: str) -> str:
        """Is a package still readable? Fallback when there's no primary
        datastore resource id."""
        return await self._probe(
            self.config.package_show_url, {"id": package_id}
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest services/scanner/tests/test_probe_availability.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add services/scanner/client.py services/scanner/tests/test_probe_availability.py
git commit -m "feat(ckan): tri-state availability probe (gone/alive/unknown)"
```

---

### Task 5: Reconcile module — probe publishable sources, flip flags

**Files:**
- Create: `services/page_builder/reconcile.py`
- Test: `services/page_builder/tests/test_reconcile.py`

**Interfaces:**
- Consumes: `store.iter_publishable_sources()`, `store.mark_source_unavailable()`, `store.clear_source_unavailable()` (Task 3); `client.probe_resource()`, `client.probe_package()` (Task 4); `pick_primary_resource_id` from `services.shared.resources`.
- Produces:
  - `async def reconcile_sources(store, client, *, concurrency: int = 4) -> dict` — probes every publishable source and applies flips. Returns `{"checked": int, "marked_unavailable": [ids], "recovered": [ids]}`.
  - `async def probe_one(client, src) -> str` — resolves a single source to `"gone"|"alive"|"unknown"` (resource probe preferred, package probe fallback).

- [ ] **Step 1: Write the failing test**

Create `services/page_builder/tests/test_reconcile.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest services/page_builder/tests/test_reconcile.py -v`
Expected: FAIL — module `reconcile` doesn't exist.

- [ ] **Step 3: Implement the reconcile module**

Create `services/page_builder/reconcile.py`:

```python
"""Weekly reconcile sweep — detect datasets removed from data.gov.il.

Dead datasets vanish from CKAN's public list, so the scanner's
`iter_all_packages` never revisits them. This sweep actively probes every
already-published source (succeeded + unavailable) and flips its flag:

  - probe "gone" (HTTP 403) + currently succeeded → mark `unavailable`
    (page preserved, archive banner). Already-unavailable stays put.
  - probe "alive" + currently unavailable → self-heal to `succeeded`.
  - probe "unknown" (404 / 5xx / transient) → leave unchanged.

Scheduling (the weekday gate + env knob) lives in the pipeline caller, not
here — this function just does one full sweep when invoked.
"""
from __future__ import annotations

import asyncio
import logging

from services.shared.firestore import FirestoreStateStore, SourceRecord
from services.shared.resources import pick_primary_resource_id

log = logging.getLogger("page_builder.reconcile")


async def probe_one(client, src: SourceRecord) -> str:
    """Resolve one source to "gone"|"alive"|"unknown". Prefers the primary
    datastore resource; falls back to the package probe when there's no
    primary resource id or the resource probe is inconclusive."""
    rid = pick_primary_resource_id(src.resources)
    if rid:
        status = await client.probe_resource(rid)
        if status != "unknown":
            return status
    return await client.probe_package(src.id)


async def reconcile_sources(
    store: FirestoreStateStore,
    client,
    *,
    concurrency: int = 4,
) -> dict:
    sources = list(store.iter_publishable_sources())
    log.info("reconcile: probing %d publishable source(s)", len(sources))
    sem = asyncio.Semaphore(concurrency)
    marked: list[str] = []
    recovered: list[str] = []

    async def _check(src: SourceRecord) -> None:
        async with sem:
            status = await probe_one(client, src)
        if status == "gone" and src.analysis_status == "succeeded":
            await asyncio.to_thread(
                store.mark_source_unavailable,
                src.id,
                "reconcile: datastore probe returned gone",
            )
            marked.append(src.id)
            log.warning("reconcile: %s removed upstream → unavailable", src.id)
        elif status == "alive" and src.analysis_status == "unavailable":
            await asyncio.to_thread(store.clear_source_unavailable, src.id)
            recovered.append(src.id)
            log.info("reconcile: %s reachable again → succeeded", src.id)

    await asyncio.gather(*[_check(s) for s in sources])
    return {
        "checked": len(sources),
        "marked_unavailable": marked,
        "recovered": recovered,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest services/page_builder/tests/test_reconcile.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add services/page_builder/reconcile.py services/page_builder/tests/test_reconcile.py
git commit -m "feat(reconcile): weekly sweep to flag/heal removed sources"
```

---

### Task 6: Wire the reconcile sweep into the pipeline (env + weekday gated)

**Files:**
- Modify: `services/page_builder/pipeline.py` (`run_pipeline`)
- Create: `services/page_builder/tests/test_reconcile_gate.py`

**Interfaces:**
- Consumes: `reconcile.reconcile_sources` (Task 5); `CKANClient` context manager.
- Produces: `run_pipeline` runs the sweep before scan when enabled+due; adds `summary["reconcile"]`. New helper `_reconcile_due(now, enabled, weekday) -> bool` (pure, testable).

- [ ] **Step 1: Write the failing test**

Create `services/page_builder/tests/test_reconcile_gate.py`:

```python
"""The reconcile gate: env knob + weekday must both pass."""
from __future__ import annotations

from datetime import datetime, timezone

from services.page_builder.pipeline import _reconcile_due


def test_disabled_never_runs():
    # Sunday (weekday()==6) but knob off.
    sunday = datetime(2026, 7, 19, 8, 0, tzinfo=timezone.utc)
    assert _reconcile_due(sunday, enabled=False, weekday=6) is False


def test_enabled_and_matching_weekday_runs():
    sunday = datetime(2026, 7, 19, 8, 0, tzinfo=timezone.utc)  # a Sunday
    assert sunday.weekday() == 6
    assert _reconcile_due(sunday, enabled=True, weekday=6) is True


def test_enabled_wrong_weekday_skips():
    monday = datetime(2026, 7, 20, 8, 0, tzinfo=timezone.utc)  # a Monday
    assert monday.weekday() == 0
    assert _reconcile_due(monday, enabled=True, weekday=6) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest services/page_builder/tests/test_reconcile_gate.py -v`
Expected: FAIL — `_reconcile_due` not defined.

- [ ] **Step 3: Add the pure gate helper**

In `services/page_builder/pipeline.py`, add near the top-level functions (e.g. before `run_pipeline`):

```python
def _reconcile_due(now: datetime, *, enabled: bool, weekday: int) -> bool:
    """Weekly reconcile runs only when enabled AND today matches the
    configured weekday (Python Monday=0 .. Sunday=6)."""
    return enabled and now.weekday() == weekday
```

- [ ] **Step 4: Run the sweep in `run_pipeline` when due**

In `run_pipeline`, after the env block that reads the selector gates and before `# [1] scan` (around line 255), add:

```python
    # [0] weekly reconcile — probe already-published sources and flag those
    # removed upstream (they vanish from CKAN's list, so the scan below
    # never revisits them). Gated by RECONCILE_ENABLED + RECONCILE_WEEKDAY
    # (Asia/Jerusalem), default off / Sunday. Full sweep, no cursor.
    reconcile_summary = None
    reconcile_enabled = os.environ.get("RECONCILE_ENABLED", "false").lower() in (
        "true", "1", "yes",
    )
    reconcile_weekday = int(os.environ.get("RECONCILE_WEEKDAY", "6"))
    try:
        from zoneinfo import ZoneInfo
        il_now = datetime.now(ZoneInfo("Asia/Jerusalem"))
    except Exception:
        il_now = datetime.now(timezone.utc)
    if not dry_run and not override_id and _reconcile_due(
        il_now, enabled=reconcile_enabled, weekday=reconcile_weekday
    ):
        from services.scanner.client import CKANClient
        from . import reconcile as _reconcile
        log.info("reconcile: due (weekday=%s) — running sweep", reconcile_weekday)
        async with CKANClient(config=config) as _ckan:
            reconcile_summary = await _reconcile.reconcile_sources(store, _ckan)
        log.info("reconcile: %s", reconcile_summary)
```

Then add it to the summary — in the `summary: dict = {...}` initializer (around line 272) add a key:

```python
        "reconcile": reconcile_summary,
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest services/page_builder/tests/test_reconcile_gate.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Regression — pipeline gate tests still pass**

Run: `pytest services/page_builder/tests/test_pipeline_gate.py -v`
Expected: PASS (the new key defaults to `None`; existing assertions unaffected).

- [ ] **Step 7: Commit**

```bash
git add services/page_builder/pipeline.py services/page_builder/tests/test_reconcile_gate.py
git commit -m "feat(pipeline): run weekly reconcile sweep (env + weekday gated)"
```

---

### Task 7: Publisher emits unavailable pages + stamps the flag

**Files:**
- Modify: `services/page_builder/publish.py` (`dataset_meta_from_source`, `run_from_firestore`)
- Test: `services/page_builder/tests/test_publish_unavailable.py`

**Interfaces:**
- Consumes: `store.iter_publishable_sources()` (Task 3); `DatasetMeta.source_status/unavailable_since` (Task 2).
- Produces: `dataset_meta_from_source` copies `source_status`/`unavailable_since` from the source; `run_from_firestore` iterates publishable (not just succeeded).

- [ ] **Step 1: Write the failing test**

Create `services/page_builder/tests/test_publish_unavailable.py`:

```python
"""Publisher preserves unavailable pages and stamps the flag into data.json."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from services.shared.firestore import SourceRecord
from services.page_builder import publish


def _src(sid: str, status: str, since: datetime | None) -> SourceRecord:
    return SourceRecord(
        id=sid,
        title="מאגר",
        slug="magar",
        organization={"name": "labor", "title": "משרד העבודה"},
        tags=["א"],
        resources=[{"id": "rid-1", "format": "CSV",
                    "url": "https://data.gov.il/dataset/x/resource/rid-1/download/x.csv"}],
        record_count=10,
        metadata_modified=datetime(2026, 5, 1, tzinfo=timezone.utc),
        analysis_status=status,
        unavailable_since=since,
        agent_data={"summary_he": "ס", "dataset_kind": "registry", "related_ids": [], "version": 1},
    )


def test_unavailable_source_is_published_with_flag(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(publish, "embed", lambda _t: None)
    since = datetime(2026, 7, 20, tzinfo=timezone.utc)
    records = [
        _src("alive-1", "succeeded", None),
        _src("dead-1", "unavailable", since),
    ]
    store = MagicMock()
    store.iter_publishable_sources.return_value = iter(records)
    store.set_embedding.side_effect = lambda *_: None

    publish.run_from_firestore(out_root=tmp_path, store=store)

    dead = json.loads((tmp_path / "datasets" / "dead-1" / "data.json").read_text())
    assert dead["source_status"] == "unavailable"
    assert dead["unavailable_since"].startswith("2026-07-20")

    alive = json.loads((tmp_path / "datasets" / "alive-1" / "data.json").read_text())
    assert alive["source_status"] == "available"
    assert "unavailable_since" not in alive  # exclude_none drops it
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest services/page_builder/tests/test_publish_unavailable.py -v`
Expected: FAIL — publisher uses `iter_succeeded_sources` (mock has no such return set / flag not copied).

- [ ] **Step 3: Copy the flag in `dataset_meta_from_source`**

In `services/page_builder/publish.py`, in `dataset_meta_from_source`, add to the `DatasetMeta(...)` constructor (after `analyzed_metadata_modified=src.analyzed_metadata_modified,`):

```python
        source_status=(
            "unavailable" if src.analysis_status == "unavailable" else "available"
        ),
        unavailable_since=src.unavailable_since,
```

- [ ] **Step 4: Iterate publishable sources**

In `run_from_firestore`, change:

```python
    sources: list[SourceRecord] = list(store.iter_succeeded_sources())
    log.info("publish: %d succeeded source(s)", len(sources))
```

to:

```python
    sources: list[SourceRecord] = list(store.iter_publishable_sources())
    log.info("publish: %d publishable source(s) (succeeded + unavailable)", len(sources))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest services/page_builder/tests/test_publish_unavailable.py -v`
Expected: PASS (1 test).

- [ ] **Step 6: Regression — existing publish tests**

The existing `test_publish.py` sets `store.iter_succeeded_sources.return_value`; it must now set `iter_publishable_sources`. Update its `_store_mock` (in `services/page_builder/tests/test_publish.py`):

```python
def _store_mock(records: list[SourceRecord]) -> MagicMock:
    store = MagicMock()
    store.iter_succeeded_sources.return_value = iter(records)
    store.iter_publishable_sources.return_value = iter(records)
    ...
```

Run: `pytest services/page_builder/tests/test_publish.py services/page_builder/tests/test_publish_unavailable.py -v`
Expected: PASS (all).

- [ ] **Step 7: Commit**

```bash
git add services/page_builder/publish.py services/page_builder/tests/test_publish_unavailable.py services/page_builder/tests/test_publish.py
git commit -m "feat(publish): preserve unavailable pages + stamp source_status flag"
```

---

### Task 8: Selector never re-picks an unavailable source

**Files:**
- Modify: `services/page_builder/selector.py` (`pick_next`, Track 2)
- Test: `services/page_builder/tests/test_selector_unavailable.py`

**Interfaces:**
- Consumes: `SourceRecord.analysis_status` (`"unavailable"`).
- Produces: Track 2 skips `unavailable` sources (so a rebuild can't 403 and drop the preserved page).

- [ ] **Step 1: Write the failing test**

Create `services/page_builder/tests/test_selector_unavailable.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest services/page_builder/tests/test_selector_unavailable.py -v`
Expected: FAIL — the source is currently picked (Track 2 gap satisfied).

- [ ] **Step 3: Add the guard in Track 2**

In `services/page_builder/selector.py`, inside the Track 2 `for src in store.list_changed_sources(...)` loop, right after the `if src.id in seen: continue` line (line ~127), add:

```python
            # A source removed upstream (reconcile flagged it `unavailable`)
            # keeps its preserved snapshot page. Re-selecting it would run an
            # agent session whose prefetch 403s → `restricted` → the page is
            # dropped, undoing the preservation. Never rebuild it here; the
            # reconcile self-heal path returns it to `succeeded` if it comes
            # back.
            if src.analysis_status == "unavailable":
                continue
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest services/page_builder/tests/test_selector_unavailable.py -v`
Expected: PASS.

- [ ] **Step 5: Regression — selector tests**

Run: `pytest services/page_builder/tests/test_selector.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add services/page_builder/selector.py services/page_builder/tests/test_selector_unavailable.py
git commit -m "fix(selector): never re-select an unavailable source (would drop its page)"
```

---

### Task 9: Frontend — page banner + explorer prop + listing badge

**Files:**
- Modify: `frontend/pages/datasets/[slug].vue` (banner + pass prop to `DatasetExplorer`)
- Modify: `frontend/components/DatasetExplorer.vue` (accept `sourceUnavailable` prop)
- Modify: `frontend/components/DatasetCard.vue` (archive badge)

**Interfaces:**
- Consumes: `entry.source_status`, `entry.unavailable_since` (Task 2 TS types).
- Produces: `DatasetExplorer` gains an optional prop `sourceUnavailable?: boolean`; when true it renders the gone-state deterministically (without waiting on the live 403).

- [ ] **Step 1: Accept the `sourceUnavailable` prop in DatasetExplorer**

In `frontend/components/DatasetExplorer.vue`, extend the props:

```ts
const props = defineProps<{
  resources: ResourceEntry[]
  primaryResourceId?: string
  recordCount?: number
  sourceUnavailable?: boolean
}>()
```

Seed the ref from the prop so SSG/first paint shows the gone-state immediately. Change:

```ts
const sourceGone = ref(false)
```

to:

```ts
const sourceGone = ref(Boolean(props.sourceUnavailable))
```

- [ ] **Step 2: Render the SSG banner + pass the prop in `[slug].vue`**

In `frontend/pages/datasets/[slug].vue`, update the explorer usage (around line 406) to pass the flag:

```html
        <DatasetExplorer
          :resources="entry.resources ?? []"
          :primary-resource-id="entry.primary_resource_id"
          :record-count="entry.record_count"
          :source-unavailable="entry.source_status === 'unavailable'"
        />
```

Add the banner immediately **before** the `<article ref="bodyEl" ...>` (line ~405), so it sits at the top of the content column:

```html
        <div
          v-if="entry.source_status === 'unavailable'"
          class="unavailable-banner"
          role="note"
        >
          <strong>מאגר זה הוסר ממקור הנתונים (data.gov.il).</strong>
          הנתונים המוצגים הם תמונת מצב מהסריקה האחרונה שלנו<template v-if="unavailableSinceHe">, שנערכה עד {{ unavailableSinceHe }}</template>.
        </div>
```

Add a computed for the formatted date near the other computeds (e.g. after `pagePath`, ~line 225). Reuse the existing date formatter used elsewhere in this file for `analyzed_metadata_modified` (match whatever helper that block uses — e.g. `formatDateHe`); if the file formats dates inline, mirror that:

```ts
const unavailableSinceHe = computed(() =>
  entry.value.unavailable_since
    ? new Date(entry.value.unavailable_since).toLocaleDateString('he-IL')
    : '',
)
```

Add scoped styling (in this file's `<style scoped>`), using design tokens (warn `#ffc107`, ink `#0c3058`):

```css
.unavailable-banner {
  border: 1px solid #ffc107;
  background: #fff9e6;
  color: #0c3058;
  border-radius: 0.5rem;
  padding: 0.75rem 1rem;
  margin-bottom: 1rem;
  font-size: 0.9rem;
  line-height: 1.5;
}
```

- [ ] **Step 3: Add the archive badge to DatasetCard**

In `frontend/components/DatasetCard.vue`, in the top badge row, add an archive badge when unavailable. Change:

```html
    <div class="flex gap-2 flex-wrap mb-2 text-xs">
      <span v-if="entry.organization" class="badge">{{ entry.organization }}</span>
      <span v-for="f in entry.formats.slice(0, 3)" :key="f" class="badge">{{ f }}</span>
    </div>
```

to:

```html
    <div class="flex gap-2 flex-wrap mb-2 text-xs">
      <span v-if="entry.source_status === 'unavailable'" class="badge badge-archive">ארכיון</span>
      <span v-if="entry.organization" class="badge">{{ entry.organization }}</span>
      <span v-for="f in entry.formats.slice(0, 3)" :key="f" class="badge">{{ f }}</span>
    </div>
```

Add a scoped style for `.badge-archive` at the end of the component (add a `<style scoped>` block if none exists):

```css
.badge-archive {
  background: #fff9e6;
  color: #8a6d00;
  border: 1px solid #ffc107;
}
```

- [ ] **Step 4: Typecheck**

Run: `cd frontend && npx nuxi typecheck`
Expected: clean (no errors from the three files).

- [ ] **Step 5: Manual drive — banner, explorer, badge**

Prepare a local `data.json` for a test dataset with `"source_status": "unavailable"` and an `"unavailable_since"` under `frontend/public/datasets/<id>/` (or run a publish from an emulator seeded via Task 3/7). Then:

Run: `cd frontend && npm run dev`
1. Open the unavailable dataset page → confirm the yellow banner renders at the top of the content, the explorer shows the gone-state (no table/download), and prose/charts still render.
2. Open `/datasets/` (listing) → confirm the "ארכיון" badge appears on that dataset's card.
3. Open an available dataset → confirm no banner, no badge, explorer works.

- [ ] **Step 6: Commit**

```bash
git add frontend/pages/datasets/[slug].vue frontend/components/DatasetExplorer.vue frontend/components/DatasetCard.vue
git commit -m "feat(frontend): archive banner + listing badge for unavailable sources"
```

---

## Rollout (after all tasks merge)

1. Phase 1 (Task 1) deploys via the normal frontend push-to-deploy — immediate relief for current dead pages.
2. Phase 2 ships with `RECONCILE_ENABLED` unset (off). Enable in prod once validated:
   ```sh
   gcloud run services update govdata-builder --region=me-west1 \
     --update-env-vars=RECONCILE_ENABLED=true
   # optional: RECONCILE_WEEKDAY=<0=Mon..6=Sun>
   ```
3. Confirm no GCS lifecycle rule expires the staging bucket's `content.html`
   (hard requirement): `gsutil lifecycle get gs://<GCS_STAGING_BUCKET>` should
   report no expiry affecting `datasets/**/content.html`.

## Notes / self-review

- **Spec coverage:** Phase 1 explorer fix (Task 1); `unavailable` status + `unavailable_since` (Tasks 2, 3); weekly full-sweep detection with env+weekday gate, no cursor (Tasks 4, 5, 6); self-heal `unavailable`→`succeeded` (Task 3 `clear_source_unavailable`, Task 5); publisher preserves + stamps (Task 7); selector exclusion (Task 8); SSG banner + explorer prop + listing badge (Task 9); `content.html` retention (Rollout step 3). All spec sections mapped.
- **Manual-verification honesty:** Frontend tasks (1, 9) have no unit tests because the repo has no frontend test runner — verification is typecheck + driving the real app, as stated in Global Constraints. Do not fabricate a test framework.
- **Type consistency:** `iter_publishable_sources`, `mark_source_unavailable`, `clear_source_unavailable`, `probe_resource`, `probe_package`, `reconcile_sources`, `probe_one`, `_reconcile_due`, `sourceGone`, `sourceUnavailable`, `source_status`, `unavailable_since` are used with identical names/signatures across the tasks that define and consume them.
