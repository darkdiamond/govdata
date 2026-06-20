# Architecture

This document explains how govil.ai turns raw
[data.gov.il](https://data.gov.il) datasets into connected, Hebrew-RTL
landing pages. For repository conventions and the detailed
"do / don't" rules, see [`CLAUDE.md`](../CLAUDE.md).

## The big picture

```
Cloud Scheduler (daily 07:00 Asia/Jerusalem)
        │
        ▼
Cloud Run: govdata-builder  (1 container, concurrency=1)
        │
        ├─ 1. Scanner   — poll CKAN, upsert sources/* into Firestore
        ├─ 2. Selector  — pick never-analyzed + retryable sources (≤ cap)
        ├─ 3. Agent runtime — one self-validating PydanticAI session per source
        │        content.html → GCS staging
        │        agent_data + usage → Firestore sources/<id>
        │
        └─ ≥1 success → dispatch the GitHub Actions publish workflow
                            │
                            ▼
                  4. Publisher — rebuild artifacts from Firestore,
                     nuxt generate, firebase deploy
```

The whole system is built around **one container** doing the work and
**one Firestore document per dataset** holding the truth. Parallelism
lives *inside* the container (`asyncio.gather` + a semaphore), never in
Cloud Run autoscaling.

## The four layers

### 1. Scanner (`services/scanner/`)

Polls the CKAN API on data.gov.il and upserts per-dataset state into
Firestore under `sources/{id}`. It owns the **factual** fields: title,
slug, license, resources, formats, record count, organization, and
`metadata_modified`. It also normalizes resource URLs from
`e.data.gov.il` (which sits behind Google IAP) to the public
`data.gov.il` host. Runs inside the builder container and is also usable
as a standalone CLI for debugging.

### 2. Builder / pipeline (`services/page_builder/pipeline.py`)

The orchestrator invoked daily by Cloud Scheduler:

1. **Scan** CKAN into Firestore.
2. **Select** every never-analyzed (or retryable-failed) source up to a
   daily cap, gated by a recency cutoff (see *Selection* below).
3. Run agent sessions **concurrently** (`asyncio.gather` bounded by a
   semaphore).
4. **Mark** results in Firestore and **trigger** the publisher if at
   least one page succeeded.

No new datasets means no build — the run goes idle and skips the publish
trigger.

### 3. Agent runtime (`services/page_builder/model_harness.py`)

Each selected dataset is handed to a [PydanticAI](https://ai.pydantic.dev/)
agent loop calling a model through [OpenRouter](https://openrouter.ai/)
(`OPENROUTER_MODEL`, default `minimax/minimax-m3`). The agent has four
tools: `bash` and `code_execution` (subprocesses in a private,
scrubbed-environment workdir), `web_fetch`, and `web_search`. The
canonical system prompt is `agent/system-prompt.md` — hand-edited and
byte-stable so providers can serve it from prefix cache.

Every session **self-validates before anything persists**: the agent's
output is parsed into the `AgentData` schema, passed through a
sanitizer, then checked by `agent/skills/check.py` (exit 0 required).
Failures retry on a fresh workdir up to `SESSION_ATTEMPTS` times.
Successful output is:

- `content.html` (body content only) → uploaded to GCS staging
- `agent_data` + usage/cost telemetry → written to `sources/<id>`

### 4. Publisher (`.github/workflows/publish.yml`)

A GitHub Actions workflow (free-tier minutes, keyless GCP auth via
Workload Identity Federation). It runs on two triggers:

- the builder dispatches it after ≥1 page succeeds, and
- any push to `main` touching `frontend/**` or the publisher code
  (push-to-deploy; rapid pushes collapse to a single run).

Its steps: rsync staged `content.html` from GCS → rematerialize all
artifacts from Firestore (`publish.py`) → `nuxt generate` →
`firebase deploy`. Fallback paths exist via Cloud Build and a local
script (`infra/publish-local.sh`).

## Data model: one document, two writers

The source of truth for everything the frontend renders is the Firestore
`sources/<id>` document. Exactly **two writers** feed it:

- the **scanner** writes CKAN facts, and
- the **builder** writes the agent's interpretive `agent_data`.

On every deploy, `services/page_builder/publish.py` rematerializes the
frontend artifacts from that single document:

| Artifact | Owner | Contents |
|----------|-------|----------|
| `frontend/public/data/manifest.json` | publisher | merged list of all datasets |
| `frontend/public/datasets/<id>/data.json` | publisher (from scanner facts) | `DatasetMeta` |
| `frontend/public/datasets/<id>/agent_data.json` | publisher (from agent fields) | `AgentData` |

GCS staging carries only `content.html`. Keeping a single writer per
file is deliberate — it prevents the two-writer drift class of bugs. The
schemas live in `services/page_builder/schema.py`.

## The agent output contract

The agent produces exactly two things, written to the per-session output
directory:

- **`content.html`** — body content only (no `<html>`/`<head>`/`<body>`;
  inline `<style>`/`<script>` allowed). The Nuxt shell
  (`frontend/layouts/default.vue` + `pages/datasets/[id].vue`) wraps it
  with shared chrome at generate time. Pre-loaded globals (ECharts,
  Leaflet, an in-house `GovExplorer`) mean the body must *not* include
  `<script src=>` for them.
- **`agent_data.json`** — interpretive fields only (`summary_he`,
  `dataset_kind`, optional `related_ids`). Factual fields are the
  scanner's job, not the agent's.

A key guardrail is **chart-data provenance**: the system prompt and the
self-check require every chart's numbers to trace back to the actual
CKAN data, because an earlier model once fabricated a chart.

## Selection and relatedness

**Selection** (`selector.py`) prioritizes recently-modified,
never-analyzed datasets first, draining that backlog before re-analyzing
already-published pages. Both tracks are gated by an effective recency
cutoff so the pipeline doesn't spend budget on long-abandoned datasets.

**Related datasets** (`related.py`) are scored deterministically,
content first:

```
1.5·same_ministry + 2·min(shared_tags, 6) + 8·cosine(embedding) + 6·agent_suggested
```

Embedding similarity (optional, via Voyage) dominates; same-ministry is
a tiebreaker. Top 5 per page. When embeddings are disabled, the score
falls back to ministry + shared-tag + agent-suggested signals.

## Tech stack

| Layer | Stack |
|-------|-------|
| Scanner / builder / publisher | Python 3.12, google-cloud-firestore, functions-framework |
| Agent loop | PydanticAI + OpenRouter |
| Frontend | Nuxt 3 (SSG), Vue 3, TypeScript, Tailwind, ECharts, Leaflet |
| State | Firestore (`sources/{id}`, `scan_runs/{run_id}`) |
| Hosting | Firebase Hosting (GCS is internal staging only) |
| Compute | Cloud Run (builder), GitHub Actions / Cloud Build (publisher) |
