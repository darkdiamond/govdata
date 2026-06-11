# Cut agent-run costs: fix sticky re-analysis + no-agent chart refresh

> **Status (2026-06-10):** the immediate pieces already shipped and are live in prod:
> - Sticky-flag fix — Track 2 skips sources whose `metadata_modified <= analyzed_metadata_modified` (commit `57e93a3`).
> - **Track 2 is fully paused** via `REANALYZE_ENABLED=false` (commit `cab5dd7`; stronger stopgap than the cooldown bump in "Rollout order" step 1, per user decision). ~135 datasets bump `metadata_modified` daily, so without structural gating they'd re-qualify every cooldown (~$350/mo). Verified: scheduler-path dry runs select `[]`.
>
> Everything below from "A. Kill the waste — structural vs additive classification" onward (gating, `viz_recipes` + shared executor, `__CHART_DATA` contract, weekly refresher, prompt trims) is **not yet implemented**. When it ships, flip `REANALYZE_ENABLED=true` together with the Track 2 structural-only filter (rollout steps 5–7).

## Context

Agent sessions (~$0.77 each, Sonnet 4.6) are ~all of the pipeline's cost: `N_PER_RUN=20` on a daily tick → up to ~$460/mo. The never-analyzed backlog (Track 1) is mostly drained, so daily slots are filled by Track 2 re-analyses. Two problems compound:

1. **Bug — sticky `change_status`.** The scanner writes `change_status` only on NEW/UPDATED (`services/scanner/main.py:81-85`); nothing ever resets it — not `mark_analysis_succeeded` (`services/shared/firestore.py:301-318`), not unchanged scans. Selector Track 2 (`services/page_builder/selector.py:78-89`) never compares `metadata_modified` vs the stored-but-unused `analyzed_metadata_modified`. Net effect: **every page ever flagged "updated" re-runs every 30 days forever**, even if CKAN never changed again.
2. **Crude change detection.** Detection is `metadata_modified` timestamp only (`services/scanner/detector.py:17-30`). Datasets that append a few rows daily/weekly look identical to real restructures, so even legitimate Track 2 picks mostly regenerate the same page with slightly fresher inlined chart numbers.

User decisions (confirmed): cut waste, no hard cap; genuinely-new datasets keep full agent runs; published pages should refresh **weekly without an agent run**; **no staleness backstop** (re-analyze only on structural change); include per-session prompt trims.

Target steady state: agent runs only for new datasets + rare structural changes (~$30–80/mo, mostly volume-driven), with chart data refreshed weekly for free.

## Design

### A. Kill the waste (selection gating)

**Day-1 fix (ship first, standalone):** in `selector.py` Track 2, skip any source where `analyzed_metadata_modified` is set and `metadata_modified <= analyzed_metadata_modified` (client-side filter; both fields already on `SourceRecord`). Also make cooldown env-configurable (`COOLDOWN_DAYS`, default 30). This alone stops the "nothing changed since analysis" rotation immediately, no schema changes.

**Structural vs additive classification:**
- Scanner: extend `services/scanner/client.py::datastore_total` to also return `result.fields` from the same `limit=0&include_total=true` call (free — no extra HTTP). `save_dataset` persists `schema_fields: [{id, type}]` for the primary resource.
- Builder: `mark_analysis_succeeded` additionally snapshots `analyzed_structure = {schema_hash, resource_ids (sorted), record_count, title_hash, notes_hash}` and resets `change_class` to `"none"`.
- Detector (`services/scanner/detector.py`): on UPDATED, when `analyzed_structure` exists, compute `change_class`:
  - `structural` if resource-id set changed, OR schema_hash changed, OR record_count outside [0.5×, 3×] of analyzed count, OR title/notes hash changed (notes render on-page).
  - `additive` otherwise. Stored via `save_dataset`. Comparing against the *analysis snapshot* (not previous scan) makes the flag self-clearing on the next successful run — eliminates the stickiness bug class structurally.
- Selector Track 2: keep the indexed `change_status in {new,updated}` query, add client-side `change_class == "structural"` filter; widen the fetch multiplier (most candidates now filter out). **No Track 3 staleness backstop** (user choice) — but keep an env knob `REANALYZE_STALE_DAYS` (default `0` = off) so it can be turned on later without code changes.
- One-shot backfill `services/page_builder/backfill_analyzed_structure.py` (pattern: `backfill_datastore_active.py`): seed `analyzed_structure` from current doc state for existing succeeded sources (today's state as baseline; prevents a thundering herd).

### B. No-agent chart refresh (recipe DSL + shared executor)

Rejected alternative: agent-emitted `refresh.py` per dataset — running ~500 drifting LLM-written scripts in the builder is unauditable and against the repo's deterministic-publisher spirit. The recipe DSL covers the agent's aggregation surface by construction (the prompt already constrains it to per-value counts, top-N, group-by/time-bucket/histogram/percentiles over ≤5000-row samples; `datastore_search_sql` is disabled upstream).

- **`services/page_builder/recipes.py` (new):** Pydantic recipe models + deterministic executor (stdlib-only so it can also run inside the agent session). Vocabulary: `total | count_by | group_agg | top_n | time_bucket | histogram | percentiles`, with `resource_id`, projection `fields`, optional `values` (fixed-value per-value `limit=0` counts), `filters`/`q`, `agg {fn, field}`, `bucket year|month|day`, `n`, `sort`, `sample_limit≤5000`, `output pairs|series|matrix`. Output per chart: `{labels, values}` / `{series}` / `{cells}` + `_meta {refreshed_at, total}`. Browser UA + retry, mirroring scanner client conventions.
- **Shared-executor guarantee:** upload `recipes.py` to the session as `recipes_exec.py` alongside `check.py` (extend `infra/upload-check-script.py`; add basename to `SESSION_INPUT_BASENAMES` in `session_runner.py:603`). Agent workflow: explore → write `viz_recipes` → run `python3 /mnt/session/uploads/recipes_exec.py …` to produce the **initial** `/mnt/session/outputs/chart_data.json` → write prose/insights from the executor's output. Build-time and refresh-time data come from identical code ⇒ no shape drift.
- **Contract change (agent prompt v2):** recipe-backed charts read `const d = window.__CHART_DATA["<chart-dom-id>"]` instead of inlined literals. Charts the DSL can't express (choropleths, ITM overlays, web-sourced baselines) stay inlined as today = non-refreshable, refreshed at next real agent run. GovMap maps already fetch live.
- **Artifact flow (single-writer respected):** `chart_data.json` is a session output "extra" — `session_runner.py:639-643` already stages extras to `gs://<staging>/datasets/<id>/`; verified the rsync exclude `.*/(data|agent_data)\.json$` (`cloudbuild-publish.yaml:32`) does NOT match `chart_data.json` (regex requires `/` immediately before `data.json`). The refresher later overwrites the same GCS object. Publisher untouched; `data.json`/`agent_data.json` stay Firestore-sourced. Add a comment in `cloudbuild-publish.yaml` + a regex unit test.
- **Frontend (`frontend/pages/datasets/[id].vue`):** in the SSG fetcher, also read `chart_data.json` (`.catch(() => null)`); when present, prepend `<script>window.__CHART_DATA = {…}</script>` to `rawBody` (serialize `<` as `<`; do NOT use `<\/` — check.py/sanitizer treat it as forbidden). Prepending into the body string makes it execute before agent scripts on initial parse AND on SPA nav (`executeBodyScripts` runs scripts in DOM order) — zero changes to that function. Pages without `chart_data.json` (all ~500 existing) are byte-identical no-ops; no backfill (would cost ~$380 of agent runs for nothing). They adopt the contract at their next structural-change run.
- **Refresh failure handling:** per-chart merge — refresher reads existing `chart_data.json` from GCS, keeps previous value for failed charts, logs WARNING, tracks `last_refresh.failures[chart_id]`; ≥3 consecutive failures for a chart ⇒ set `change_class = "structural"` (vanished column ⇒ real re-run).
- **Schema:** `AgentData.viz_recipes: Optional[...]` (`schema.py`, `extra='allow'` already permits); **exclude `viz_recipes` from the public `agent_data.json`** in `publish.py` (interpretive-only contract) — recipes live on the Firestore doc and are read by the refresher from there. Optional: `DatasetMeta.charts_refreshed_at` sourced from `sources/<id>.last_refresh.at` for on-page vintage display.
- **check.py v2:** accept optional chart_data arg; validate recipe schema, every `__CHART_DATA["x"]` reference resolves to a recipe/chart_data key, chart_data ≤100KB, valid JSON.

### C. Scheduling + publish (weekly refresh)

- New refresher step in `services/page_builder/pipeline.py::run_pipeline` after the agent gather, plus a `{"refresh_only": true}` HTTP flag in `main.py` for manual runs. Same container, same daily 07:00 tick — no new service, no autoscaling.
- Due set (client-side filter over succeeded sources, ~500 docs): `viz_recipes` present AND `last_refresh.at` older than `REFRESH_INTERVAL_DAYS` (default **7** — user chose weekly) AND `max(resource.last_modified…, metadata_modified) > last_refresh.at` (skip datasets whose data didn't move). Cap `REFRESH_PER_RUN` (default 150), `asyncio.Semaphore(8)`, politeness delay. Firestore: new `FirestoreStateStore.set_last_refresh`.
- Publish trigger condition becomes `succeeded_ids or refreshed_ids`. Refresh-only days cost ~$0.05–0.10 of Cloud Build (~$2–3/mo worst case).
- Env knobs in `infra/builder.deploy.sh`: `COOLDOWN_DAYS`, `REANALYZE_STALE_DAYS=0`, `REFRESH_ENABLED`, `REFRESH_INTERVAL_DAYS=7`, `REFRESH_PER_RUN`.

### D. Per-session trims (bundled with prompt v2)

1. Prompt: "write `content.html` exactly once after exploration; on check.py failure use targeted `edit` on the failing part, never rewrite the file" — file rewrites are the largest output-token sink (~24k avg output).
2. Remove the contradictory `const GOVIL_PALETTE = [/* copy from above */]` / `baseECharts` lines from the REFERENCE SKELETON (`agent/govdata-agent.yaml:469-470`) — they bait re-emission against the "use `window.GovEcharts`, do NOT redefine" rule.
3. Trim legacy GovExplorer-shim mentions from the cached prefix.

## Files to modify

| File | Change |
|---|---|
| `services/page_builder/selector.py` | Day-1 `analyzed_metadata_modified` filter; env cooldown; structural filter; `REANALYZE_STALE_DAYS` knob (default off); widen fetch multiplier |
| `services/page_builder/recipes.py` (new) | Recipe models + deterministic executor (stdlib CLI mode for in-session use) |
| `services/scanner/client.py` / `main.py` | Return + persist `schema_fields` from the existing limit=0 call |
| `services/scanner/detector.py` | `classify_change()` → `change_class` vs `analyzed_structure` |
| `services/shared/firestore.py` | `save_dataset` (schema_fields, change_class), `mark_analysis_succeeded` (snapshot + reset), `set_last_refresh`, `SourceRecord` fields |
| `services/page_builder/pipeline.py` / `main.py` | Refresher step, `refresh_only` flag, publish condition `succeeded or refreshed` |
| `services/page_builder/session_runner.py` | Handle `chart_data.json` output; validate recipes; add `recipes_exec.py` to `SESSION_INPUT_BASENAMES` |
| `services/page_builder/schema.py` / `publish.py` | `viz_recipes` field (excluded from public agent_data.json); optional `charts_refreshed_at` |
| `agent/skills/check.py` | Recipe/chart_data validation rules |
| `agent/govdata-agent.yaml` | Prompt v2: recipes workflow, `__CHART_DATA` contract, Area D trims |
| `infra/upload-check-script.py`, `infra/builder.deploy.sh` | Upload `recipes_exec.py`; new env vars |
| `frontend/pages/datasets/[id].vue` | Read + prepend chart_data script to body |
| `services/page_builder/backfill_analyzed_structure.py` (new) | One-shot baseline seeding |
| `cloudbuild-publish.yaml` | Comment documenting chart_data.json passes the rsync exclude |

## Rollout order (dependencies matter)

1. **Day-1 fix**: selector `analyzed_metadata_modified` filter + env cooldown → deploy builder. Immediate large cut, zero risk.
2. `recipes.py` + tests; check.py v2; upload `recipes_exec.py`; schema + session_runner changes (inert until prompt changes).
3. Frontend `[id].vue` injection (backward-compatible no-op); ships via normal publish.
4. **Agent prompt v2** via `infra/update-agent.py` (recipes workflow + Area D trims); canary one dataset (`--source <id>`); verify chart renders from `__CHART_DATA`, check.py passes, page looks right. *Must precede gating flip so structural re-runs produce refreshable pages.*
5. Scanner schema capture + classification; builder snapshot; run `backfill_analyzed_structure`.
6. Flip Track 2 to structural-only.
7. Enable refresher (`REFRESH_ENABLED=true`, `REFRESH_PER_RUN=50` first week, then raise).

## Cost impact

| | Today | After |
|---|---|---|
| Agent sessions/day | up to 20 (mostly redundant) | new datasets + rare structural (~1–3/day) |
| Agent $/mo | ~$460 | ~$30–80 (volume-driven) |
| Refresher | — | ~$0 compute + ≤$3/mo Cloud Build |
| Chart freshness | frozen ≥30d | weekly where data moved |

## Verification

- Unit: detector classification matrix; selector tracks vs Firestore emulator (including the day-1 filter); recipe executor vs recorded CKAN fixture JSON; check.py rules; rsync-exclude regex test for `chart_data.json`.
- Local e2e (CLAUDE.md flow): emulator + `python -m services.page_builder.pipeline --source <id> --no-trigger-publish` with prompt v2 → `npm run generate` → verify chart renders from `__CHART_DATA`, then SPA-nav away and back (script re-execution order).
- Prod canary: one dataset build → one `refresh_only` invocation → confirm GCS object overwritten and deployed page shows new numbers with intact prose.
- Monitor a week: `scan_runs`, selected IDs, Anthropic console spend, refresher WARNING rate.

## Risks / open items

- **DSL coverage**: before freezing the vocabulary, audit ~20 existing `content.html` script blocks (all in `frontend/public/datasets/`) to confirm the verbs cover ≥90% of charts; non-covered charts degrade gracefully to static.
- **Prose drift**: refreshed chart data can diverge from baked insight bullets (e.g., top category flips). Accepted for v1 (no staleness backstop per user choice). Future option: refresher flags `change_class=structural` when a chart's argmax flips.
- **CKAN behavior**: assumed `metadata_modified` bumps on schema-only changes; if not, the record-count band + resource-set checks still catch most restructures.
- **WAF/rate limits on refresher**: low initial `REFRESH_PER_RUN`, politeness delay, failures degrade to stale-but-valid data.
