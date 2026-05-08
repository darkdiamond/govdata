# CLAUDE.md — repository conventions for Claude Code sessions

This file is loaded automatically. Read it before touching code.

## What this project is

A pipeline that turns data.gov.il datasets into connected, Hebrew-RTL
landing pages. Four layers:

1. **Scanner** — `services/scanner/`. Polls CKAN, upserts per-source
   state into **Firestore** (`sources/*`). Runs inside the builder
   container; also usable as a local CLI for debugging.
2. **Builder** — `services/page_builder/`. **Cloud Run service**
   (`govdata-builder`). One HTTP invocation per scheduler tick:
   - `pipeline.run_pipeline` drives scan → select N sources → agent
     sessions via `asyncio.gather` → mark Firestore → trigger publisher.
   - Pinned to **one container** (`--max-instances=1 --concurrency=1`).
     Per-source parallelism is `asyncio.gather` inside that container
     (agent streams are I/O-bound), never Cloud Run autoscaling.
3. **Managed Agent** — `agent/*.yaml` + `agent/skills/`. Anthropic-hosted,
   `claude-sonnet-4-6` in a per-session container. Writes `content.html`
   (body) + `data.json` (manifest entry). Tools: bash, web_search,
   web_fetch, code_execution, file writing.
4. **Publisher** — `cloudbuild-publish.yaml`. Cloud Build job triggered by
   the builder at the end of a successful run. rsyncs staged pages from
   GCS → `frontend/public/datasets/`, regenerates
   `frontend/public/data/manifest.json` from Firestore, runs
   `nuxt generate`, then `firebase deploy --only hosting`.

State: Firestore `sources/{id}` (per-dataset), `scan_runs/{run_id}`
(per invocation). No SQLite. No Cloudflare.

## Critical conventions

- **Hebrew-first, RTL everywhere.** `<html dir="rtl" lang="he">`. Body
  line-height `1.5` (gov.il standard). Tailwind logical properties
  (`ps-*`/`pe-*`) when using Tailwind.
- **Model**: `claude-sonnet-4-6`. Do not upgrade to Opus without asking.
  New Claude calls follow the `claude-api` skill: adaptive thinking,
  prompt caching, no `budget_tokens`, no `temperature`/`top_p`/`top_k`
  on 4.6+.
- **Design tokens** (aligned with www.gov.il — mirrored across
  `frontend/tailwind.config.ts`,
  `services/page_builder/templates/dataset_page.html.j2`, and
  the `system:` block of `agent/govdata-agent.yaml`):
  primary `#0068f5` (hover `#0053c4`), ink `#0c3058`, ink-deep `#0b3668`,
  surface `#f1f7ff`, surface-alt `#f0f4fa`, rule `#c3cfe7`, subtle
  `#6c757d`. Semantic: ok `#198754`, warn `#ffc107`, danger `#dc3545`,
  info `#0dcaf0`. Header gradient `#025fdb → #0b3668`. Font: **Rubik
  only** (no Heebo). Radii: `rounded-gov` = 0.5rem (cards/buttons),
  `rounded-gov-sm` = 0.2rem (badges), `rounded-gov-pill` = 50rem
  (chips). Container `max-w-gov` = 1400px. Icons: Lucide SVGs committed
  to `frontend/public/icons/`.
- **Pre-loaded dataset-page globals** (head scripts; see
  `frontend/utils/dataset-libs.ts` and `awaitDatasetLibs()` in
  `frontend/pages/datasets/[id].vue`): `echarts`, `L`,
  `L.markerClusterGroup`, and `GovExplorer` (in-house;
  `frontend/public/lib/gov-explorer.js`). Agent bodies use them as
  globals and must NOT include `<script src=>` for any of them.
- **Agent outputs** are a contract:
  - `/mnt/session/outputs/content.html` — body content only. No
    `<html>`/`<head>`/`<body>`. Inline `<style>` and `<script>` tags OK.
  - `/mnt/session/outputs/agent_data.json` — an `AgentData`
    (`services/page_builder/schema.py`). Holds ONLY interpretive fields
    (`summary_he`, `dataset_kind`, optional `related_ids`). Scanner
    facts (id, title, slug, license, resources, formats, record_count,
    metadata_modified) are not the agent's responsibility — `data.json`
    is owned by the publisher and rebuilt from Firestore.
- **Source of truth** for everything the frontend renders is the
  Firestore `sources/<id>` document. Two writers feed it:
  scanner (CKAN facts: title, slug, license, resources, record_count,
  formats, organization, metadata_modified) and builder (agent's
  `agent_data` field). On every deploy, `services.page_builder.publish`
  rematerializes from that single doc:
    `frontend/public/data/manifest.json`        — merged ManifestEntry list
    `frontend/public/datasets/<id>/data.json`   — DatasetMeta (scanner)
    `frontend/public/datasets/<id>/agent_data.json` — AgentData (agent)
  GCS staging carries only `content.html`. Don't reintroduce a path that
  rsyncs `data.json` from GCS — single writer per file is the whole point.
- **Selection priority** (`services/page_builder/selector.py`):
  Both tracks are gated by an effective cutoff =
  `max(min_modified_floor, now - max_age_days)`. Defaults:
  `min_modified_floor = 2026-01-01 UTC`, `max_age_days = 365`. A source
  is only eligible if its CKAN `metadata_modified` is on/after that
  cutoff. Today the floor wins (we publish only 2026+ datasets);
  starting some time in 2027 the rolling 365-day window overtakes the
  floor and early-2026 pages age out naturally. gov.il has ~700
  archival/abandoned datasets we'd rather not burn agent budget on
  unless CKAN flags them as updated again.
  1. `analysis_status == "never"` AND `metadata_modified >= cutoff` —
     ordered by `metadata_modified` DESC.
  2. `change_status in {new, updated}` AND `metadata_modified >= cutoff`
     AND (`last_analyzed_at` null or older than 14 days) — ordered by
     `metadata_modified` DESC.
  The (recent) never-analyzed backlog is drained first; re-analysis of
  already-published pages waits until every recent source has at least
  one page. The 14-day cooldown applies only to Track 2 (already-
  analyzed sources that CKAN re-flagged as `updated`): skip the rebuild
  if the source was analyzed less than 14 days ago.
- **Related-datasets scoring** (deterministic, content-first):
  `1.5·same_ministry + 2·min(shared_tag_count, 6) + 8·cosine(embedding) + 6·agent_suggested`.
  Embedding similarity dominates; same-ministry is a tiebreaker only.
  Top 5 per page. Defined in `services/page_builder/related.py`.

## Key files to read before editing

| Area | File | Why |
|------|------|-----|
| Pipeline orchestration | `services/page_builder/pipeline.py` | scan → select → asyncio.gather → mark → trigger publish |
| Source selection | `services/page_builder/selector.py` | Cooldown + priority query |
| Firestore layer | `services/shared/firestore.py` | `FirestoreStateStore`, schema, queries |
| Session orchestration | `services/page_builder/session_runner.py` | Stream agent until idle; download agent_data.json + content.html; persist agent_data on the source doc; stage content.html to GCS |
| Publisher | `services/page_builder/publish.py` | Reads each succeeded `sources/<id>` and writes data.json, agent_data.json, manifest.json (single source of truth) |
| Agent behavior | `agent/govdata-agent.yaml` | Single source of truth for the agent's system prompt — design tokens, output contract, chart palette, RTL snippets, mobile rules, GovMap/GovExplorer recipes. Pushed via `infra/update-agent.py`; the Managed Agents runtime auto-caches it across the agent's tool-loop iterations within a session (~95% of input tokens served from cache, verified 2026-05-05). |
| Dataset page shell | `frontend/pages/datasets/[id].vue` | Reads data.json + agent_data.json + content.html, merges into one entry, wraps in default layout |
| Page chrome | `frontend/layouts/default.vue` | Header/footer — sole source of truth, inherited by every page including datasets |
| Schema | `services/page_builder/schema.py` | `DatasetMeta` (scanner) + `AgentData` (agent) + merged `ManifestEntry` — split contract |
| Slug helper | `services/shared/slug.py` | Deterministic Hebrew→Latin slug used by the scanner |
| Cloud Build pipeline | `cloudbuild-publish.yaml` | rsync content.html only → run publisher (writes data.json + agent_data.json + manifest.json from Firestore) → `nuxt generate` → Firebase deploy |
| Hosting config | `firebase.json`, `.firebaserc` | Firebase Hosting target + project binding |

## Conventions you will be tempted to violate (don't)

- **Don't restore SQLite or add a fallback store.** Firestore is the
  only state store. `FIRESTORE_EMULATOR_HOST` for local/test is fine.
- **Don't autoscale the builder.** `--max-instances=1 --concurrency=1`
  is deliberate. Parallelism across sources lives in `asyncio.gather`
  inside the single container. If N_PER_RUN grows past ~20, bump
  `--memory` on that one container, not instance count.
- **Don't add LLM fallbacks or mock analyzers.** Production must use
  Managed Agents (the user explicitly asked to remove these earlier).
- **Don't resurrect the viz taxonomy.** The agent picks libraries per
  dataset. Any code that hardcodes `VizType` / `VizSpec` is obsolete.
- **Agent output is body-only.** The agent writes `content.html` (no
  `<html>/<head>/<body>/<header>/<footer>`) and `agent_data.json`
  (interpretive fields only). `content.html` is staged to GCS and
  rsynced into `frontend/public/datasets/<id>/`; `agent_data.json` is
  not — its content goes through Firestore (`sources/<id>.agent_data`)
  and the publisher writes the per-dataset `agent_data.json` from there.
  `frontend/pages/datasets/[id].vue` reads all three artifacts at
  `nuxt generate` time and wraps them in the default layout via
  `v-html`. In SSG the `<script>` tags inside the body land in the
  static HTML and execute on browser load before Vue hydrates, so
  ECharts/Leaflet still work. **Don't restore a Jinja wrapper** or
  hand-roll chrome in agent output — `layouts/default.vue` is the
  single source of truth.
- **Don't reintroduce GCS-as-data.json.** Per-dataset `data.json` and
  `agent_data.json` are *only* written by `services.page_builder.publish`
  from Firestore. If they show up in `gs://<staging>/datasets/<id>/`,
  the rsync step in `cloudbuild-publish.yaml` deletes them after sync —
  by design, so the two-writer drift class can't recur.
- **Resource URLs use `data.gov.il` (no `e.`).** CKAN publishes resource
  URLs on `e.data.gov.il`, which sits behind Google IAP and redirects
  anonymous visitors to an OAuth consent screen. The scanner normalizes
  on ingest (`services/scanner/models.py::_public_resource_url`), the
  agent's HARD CONSTRAINTS + self-check enforce it on output, and the
  Nuxt route regex-rewrites the body as a final belt. Don't skip any of
  those layers — defense in depth.
- **Don't set client-side wall-clock timeouts** on the agent session.
  Only the Cloud Run timeout (3600 s) bounds it.
- **Don't bring back Cloudflare or GCS-as-CDN.** Firebase Hosting is the
  sole deploy target. GCS is an internal staging bucket only.

## Gotchas + open issues

- **Hebrew tag URLs need `experimental.payloadExtraction: false`**.
  Tag URLs are Hebrew (`/tags/אבטחה/`, `/tags/אגף-תכנון/` for multi-word
  tags); the publisher's `tag_slugs` map normalizes whitespace +
  URL-reserved chars to `-` and keeps the Hebrew letters. The
  `payloadExtraction: false` flag in `frontend/nuxt.config.ts` is
  load-bearing: with it on, Nuxt 3.21's renderer puts the raw decoded
  URL into an `x-nitro-prerender` HTTP header to hint payload
  prerender, and HTTP header values are Latin-1 only — any Hebrew
  character throws `Cannot convert argument to a ByteString` and the
  whole route returns 500. Don't re-enable payload extraction without a
  Nuxt fix.
- **Voyage embeddings are gated by `VOYAGE_ENABLED` (default off).**
  Currently disabled for cost. The secret binding (`VOYAGE_API_KEY`
  from Secret Manager) and call sites stay wired so re-enabling is a
  one-line toggle: `gcloud run services update govdata-builder
  --region=me-west1 --update-env-vars=VOYAGE_ENABLED=true`. While off,
  `embed()` short-circuits to `None` and `related.py` falls back to
  ministry + shared-tag (CKAN ∪ agent `suggested_tags`) + agent-suggested
  scoring. Existing embeddings already cached on `sources/<id>.embedding`
  keep contributing for those docs at zero new cost. Model defaults to
  `voyage-4` (1024-dim), overridable via `VOYAGE_MODEL`. To retro-fill
  embeddings on already-published sources (requires re-enable), run
  `python -m services.page_builder.backfill_embeddings`.
- **Cloud Build trigger connection** is a manual step in `bootstrap.sh`.
  Cloud Build can't check out arbitrary filesystems — it needs either a
  GitHub 2nd-gen connection or a Cloud Source Repositories mirror.
  `infra/bootstrap.sh` prints the exact `gcloud builds triggers create
  manual` command after the connection exists.
- **Anthropic SDK**: minimum `0.92.0` for
  `client.beta.files.list(scope_id=...)`.

## Running things locally

```sh
source venv/bin/activate

# Firestore emulator (so nothing hits prod)
gcloud emulators firestore start --host-port=localhost:8080 &
export FIRESTORE_EMULATOR_HOST=localhost:8080 FIRESTORE_PROJECT_ID=local-dev

# Seed a few sources via the scanner CLI
python -m services.scanner.main scan --limit 5

# Check selector output (no agent run)
python -m services.page_builder.pipeline --dry-run

# Full pipeline for a specific dataset (requires ANTHROPIC_* + GCS_STAGING_BUCKET)
python -m services.page_builder.pipeline --source <dataset_id> --no-trigger-publish

# Rebuild manifest from the emulator
python -m services.page_builder.manifest --from-firestore \
  --out frontend/public/data/manifest.json

# Frontend
cd frontend && npm run generate && npx serve .output/public
```

For cloud smoke + deploy, see `infra/DEPLOY.md`.

## Memory

Feedback memories live under `~/.claude/projects/-mnt-d-workdir-govdata/memory/`.
If the user gives feedback that changes approach, save it as a feedback
memory so future sessions don't re-litigate.
