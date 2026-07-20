# Design: graceful handling of datasets removed from the source

**Date:** 2026-07-20
**Status:** approved (pending spec review)

## Problem

When a dataset is made private / removed at data.gov.il *after* we have
already built and published its page, the page appears broken to visitors:

- The static content (agent prose + any charts baked into `content.html`)
  still renders — it is frozen at build time and does not depend on the
  live source.
- But the **data explorer** (`frontend/components/DatasetExplorer.vue`)
  fetches every row **live from the browser** via CKAN
  `datastore_search` on each page view. When the source is gone that call
  returns **HTTP 403** ("Authorization Error — user has no permission to
  read this resource").
- The explorer's schema probe (`loadSchema`, a `limit=0` call) catches
  *any* failure and returns `null`, which `activate()` treats identically
  to "resource was never datastore-backed" → it drops the resource and
  sets `collapsed = true` → the entire explorer `<section>` is removed
  from the DOM.

Result: the reader sees a data-less page with no explanation. On a
prose-only page (no charts) it looks completely empty.

**Confirmed live (2026-07-20):** three משרד העבודה licensing registries
(`a698417e`, `bc0e0381`, `8152ebdf`) now 403 on both `package_show` and
`datastore_search`, while a consolidated replacement (`90b08091`,
"מאגר קבלני כוח אדם, שירותי אבטחה וניקיון, לשכות פרטיות ועגורנים") is
public. The ministry consolidated several per-topic registries into one and
unpublished the originals.

## Goal

When a source goes offline, **keep presenting the last snapshot** (prose +
charts, which are already static) and **clearly flag that the source is no
longer available** — rather than silently hiding the explorer or dropping
the page. Row-level table data is **not** archived (we never persisted it);
the explorer is marked "gone" instead of showing rows.

## Non-goals

- Archiving the datastore rows so the explorer keeps working from an
  archive. Explicitly out of scope — the explorer shows a "gone" state, no
  table.
- Changing behaviour for sources that 403 **before** they were ever
  successfully built. Those keep today's `restricted` behaviour (parked,
  no page) — there is no snapshot to preserve.

---

## Phase 1 — Explorer stops vanishing (frontend only)

**Scope:** `frontend/components/DatasetExplorer.vue` only. No backend,
schema, or publisher change. Ships and is validated on its own.

### Behaviour change

Distinguish an **access-revoked (403)** response from a genuine
"not-datastore-backed" (404 / CKAN reject) response and from a transient
network failure.

- `dsSearch()`: on `!res.ok`, throw an error that carries the HTTP
  **status** (e.g. an `Error` with a `status` property), instead of the
  current bare `Error('http 403')` string.
- New reactive `sourceGone = ref(false)`.
- `loadSchema()` / `loadPage()`: when the failure is a **403**, set
  `sourceGone.value = true`. Do **not** treat it as the "drop this
  resource" path.
- `activate()`: if `sourceGone` is set after the probe, keep the section
  visible (do **not** add to `droppedRids`, do **not** set
  `collapsed = true`).

### Rendering

New render branch with **highest priority** inside the explorer
`<section>` (above `schemaEmpty`, table, and `fetchError`):

- When `sourceGone`: render a gone-state notice, e.g.
  > ⚠ מאגר זה אינו זמין עוד במקור הנתונים (data.gov.il). הנתונים המוצגים
  > בעמוד הם תמונת מצב מהסריקה האחרונה.
- In the gone-state: **no** search input, **no** table, **no**
  pagination, and **no "להורדת הקובץ" download link** (the resource URL is
  dead too — per explicit user instruction).

The `<section v-if="visibleCandidates.length && !collapsed">` guard stays;
because a 403 no longer collapses, the section remains rendered and shows
the gone-state.

### Unchanged (regression guard)

- **404 / "ckan reject" / not-datastore-backed** → still drops the
  resource / collapses the section (correct — those never had a table).
- **Transient failure *after* schema loaded** (`loadPage` non-403) → still
  shows the existing red `fetchError` state ("לא ניתן לטעון את הנתונים
  כעת") **with** its download link (source may still be alive; retry is
  meaningful).
- Multi-resource datasets: a 403 on one resource marks the whole source
  gone (consistent with a private package). Acceptable — partial private
  resources within a still-public package are not a real data.gov.il
  pattern we need to model.

### Phase 1 verification

- Drive `DatasetExplorer` against a known-dead resource (e.g.
  `00a3819e-…`, the `a698417e` primary) and confirm the gone-state renders
  and the section does **not** collapse.
- Drive it against a known-live resource (e.g. `243fe1ce-…` from
  `90b08091`) and confirm the table still loads normally.
- Confirm a non-datastore resource still collapses (no regression).

---

## Phase 2 — Authoritative flag + banner + listing badge (backend)

**Scope:** scanner reconcile pass, Firestore layer, schema, publisher,
frontend page + listing card. Ships after Phase 1.

### Status model

- Introduce a new `analysis_status` value: **`unavailable`**.
  - Meaning: a source that was **previously `succeeded`** (has a published
    page) but is now gone upstream. **The page is preserved.**
  - Distinct from the existing **`restricted`** (never-succeeded 403 → no
    page, parked). `restricted` behaviour is unchanged.
- New Firestore field on the source doc: **`unavailable_since`**
  (ISO timestamp), set when the doc first transitions to `unavailable`.

### Detection — weekly full sweep (simple, no cursor)

The dead datasets vanish from CKAN's public list, so the scanner's
`iter_all_packages` never revisits them. Add a **reconcile pass** to the
daily pipeline:

- Gated by env knob **`RECONCILE_ENABLED`** (default `false` — incremental
  rollout).
- Runs only when enabled **and** today's weekday (Asia/Jerusalem) matches
  **`RECONCILE_WEEKDAY`** (default e.g. `6` = Sunday). This is the entire
  scheduling logic — **no rotating slice, no per-source `last_probed`
  cursor, no state machine.** On the matching day it probes **all**
  `succeeded` + `unavailable` sources.
- Per source: a lightweight probe — `datastore_search?resource_id=<primary>&limit=0`
  (fallback `package_show` when there is no primary resource id).
  - **403 (gone):** if currently `succeeded` → mark `unavailable` +
    stamp `unavailable_since`. If already `unavailable` → leave as-is
    (do not re-stamp).
  - **200 (alive again):** if currently `unavailable` → flip back to
    **`succeeded`** and clear `unavailable_since` (self-heal). Deliberately
    **not** `→never`: the existing page is still valid, and `never` would
    drop it from the publisher until a fresh agent run completes, causing a
    temporary disappearance. Any genuine data change while it was gone is
    picked up by normal Track-2 re-analysis once CKAN's `metadata_modified`
    advances — no special handling needed here.
  - **Other errors (5xx / network):** leave unchanged (no flip on
    transient failures — err toward keeping the page live).
- Bounded concurrency (reuse the scanner's existing HTTP client / a
  `Semaphore`), sequential-ish; a few hundred `limit=0` probes complete in
  minutes, well within the 3600s Cloud Run batch timeout.

New Firestore helpers in `services/shared/firestore.py`:
- `mark_source_unavailable(dataset_id, error)` — sets
  `analysis_status="unavailable"`, `unavailable_since` (only if not
  already set), `last_error`. Does **not** bump `failed_attempts`.
- `clear_source_unavailable(dataset_id)` — flips `unavailable` back to
  `succeeded` and clears `unavailable_since`.
- An iterator over `succeeded` + `unavailable` sources for the sweep.

### Selection

- `selector.py`: `unavailable` sources are **not** eligible for rebuild
  (same exclusion as `restricted`). Only the reconcile self-heal path (or
  a genuine CKAN reappearance) returns them to circulation.

### Publisher

`services/page_builder/publish.py`:
- Include `unavailable` docs in the publish set (currently
  `iter_succeeded_sources()` → succeeded only). Their snapshot is fully
  recoverable: `content.html` persists in GCS staging, and scanner facts +
  `agent_data` are frozen in the Firestore doc.
- Stamp two new fields into `data.json` and `manifest.json` /
  `search-index.json` entries:
  - `source_status`: `"available"` | `"unavailable"`
  - `unavailable_since`: ISO date | null

### Schema

`services/page_builder/schema.py` (and the mirrored
`frontend/types/manifest.ts`): add `source_status` + `unavailable_since`
to `DatasetMeta`, `ManifestEntry`, and `SlimEntry` (keep the publisher
field set in sync with `SlimEntry` per the existing belt).

### Frontend

- `frontend/pages/datasets/[slug].vue`: when
  `source_status === "unavailable"`, render an **SSG top banner** (in the
  static HTML, SEO-safe), e.g.
  > מאגר זה הוסר ממקור הנתונים (data.gov.il) בתאריך {unavailable_since}.
  > הנתונים המוצגים הם תמונת מצב מהסריקה האחרונה שלנו.

  Pass the flag down to `DatasetExplorer` (new optional prop
  `sourceUnavailable`) so it renders the gone-state deterministically
  without waiting on the live 403 probe. The Phase-1 client-side 403
  detection remains as a belt for sources not yet caught by the weekly
  sweep.
- `frontend/components/DatasetCard.vue` (listing grid): show an
  "ארכיון" / "לא זמין במקור" badge when `source_status === "unavailable"`.

### Phase 2 verification

- Emulator: seed a `succeeded` source pointing at a dead resource, run the
  reconcile sweep, assert the doc flips to `unavailable` with
  `unavailable_since`.
- Seed an `unavailable` source pointing at a live resource, run the sweep,
  assert it self-heals.
- Run the publisher from the emulator; assert the `unavailable` page is
  still emitted and carries `source_status`/`unavailable_since` in
  `data.json` + manifest.
- Build the frontend; assert the SSG banner appears on the page and the
  badge appears on the card.
- Assert the weekday gate: sweep is a no-op on non-matching days and when
  `RECONCILE_ENABLED=false`.

---

## Rollout

1. Phase 1 merges and deploys via the normal frontend push-to-deploy.
   Immediate relief for all current dead pages.
2. Phase 2 merges with `RECONCILE_ENABLED=false`. Enable in prod with a
   single env update once validated:
   `gcloud run services update govdata-builder --region=me-west1
   --update-env-vars=RECONCILE_ENABLED=true` (optionally
   `RECONCILE_WEEKDAY=<n>`).

## Open risks / notes

- **GCS `content.html` retention:** Phase 2 assumes the staged
  `content.html` for an `unavailable` source is not purged. The publisher
  rsync deletes stray `data.json`/`agent_data.json` from GCS but keeps
  `content.html`; confirm no lifecycle rule expires it. If it can be
  purged, the page would lose its body — mitigation is out of scope but
  should be noted during Phase 2 implementation.
- The weekly full sweep re-probes healthy sources every week; this is
  intentional and cheap. If the succeeded set grows into the thousands,
  revisit (rotating slice) — but not before.
