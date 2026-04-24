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
  `agent/skills/govdata-design/SKILL.md`):
  primary `#0068f5` (hover `#0053c4`), ink `#0c3058`, ink-deep `#0b3668`,
  surface `#f1f7ff`, surface-alt `#f0f4fa`, rule `#c3cfe7`, subtle
  `#6c757d`. Semantic: ok `#198754`, warn `#ffc107`, danger `#dc3545`,
  info `#0dcaf0`. Header gradient `#025fdb → #0b3668`. Font: **Rubik
  only** (no Heebo). Radii: `rounded-gov` = 0.5rem (cards/buttons),
  `rounded-gov-sm` = 0.2rem (badges), `rounded-gov-pill` = 50rem
  (chips). Container `max-w-gov` = 1400px. Icons: Lucide SVGs committed
  to `frontend/public/icons/`.
- **Agent outputs** are a contract:
  - `/mnt/session/outputs/content.html` — body content only. No
    `<html>`/`<head>`/`<body>`. Inline `<style>` and `<script>` tags OK.
  - `/mnt/session/outputs/data.json` — a `ManifestEntry`
    (`services/page_builder/schema.py`).
- **Source of truth** for what the home/category pages show is Firestore
  `sources` where `analysis_status == "succeeded"`. The builder stores
  the enriched `ManifestEntry` inline on each successful source doc; the
  publisher rematerializes `manifest.json` from that on every deploy.
- **Selection priority** (`services/page_builder/selector.py`):
  1. `change_status in {new, updated}` AND (`last_analyzed_at` null or
     older than 7 days) — ordered by `metadata_modified` DESC.
  2. `analysis_status == "never"` — ordered by `metadata_modified` DESC.
  The 7-day cooldown only applies to Track 1; never-analyzed sources are
  always eligible via Track 2.
- **Related-datasets scoring** (unchanged, deterministic):
  `5·same_ministry + 2·min(shared_tag_count, 6) + 3·cosine(embedding) + 4·agent_suggested`.
  Top 5 per page. Defined in `services/page_builder/related.py`.

## Key files to read before editing

| Area | File | Why |
|------|------|-----|
| Pipeline orchestration | `services/page_builder/pipeline.py` | scan → select → asyncio.gather → mark → trigger publish |
| Source selection | `services/page_builder/selector.py` | Cooldown + priority query |
| Firestore layer | `services/shared/firestore.py` | `FirestoreStateStore`, schema, queries |
| Session orchestration | `services/page_builder/session_runner.py` | Stream-first terminal-idle gate, GCS staging |
| Agent behavior | `agent/govdata-agent.yaml` | Agent's system prompt. Skill content is inlined because the skill file is not sent to the runtime. |
| Agent design | `agent/skills/govdata-design/SKILL.md` | Design tokens + output contract + chart palette + RTL snippets |
| Page chrome | `services/page_builder/templates/dataset_page.html.j2` | Shared header/breadcrumb/related/footer |
| Schema | `services/page_builder/schema.py` | `ManifestEntry` — boundary between agent + builder + frontend |
| Publisher | `cloudbuild-publish.yaml` | Generate Nuxt site + Firebase deploy |
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
- **Don't add a Nuxt route for `/datasets/[id]`.** Dataset pages are
  agent-authored HTML placed at `frontend/public/datasets/<id>/` by
  the publisher; Nuxt serves them as static assets, not through SSR.
  Category routes (`/ministries/[slug]`, `/tags/[slug]`, `/kinds/[kind]`)
  are the only dynamic ones Nuxt owns.
- **Don't set client-side wall-clock timeouts** on the agent session.
  Only the Cloud Run timeout (3600 s) bounds it.
- **Don't push to `main` without asking.** Commits yes; pushes require
  explicit branch confirmation.
- **Don't bring back Cloudflare or GCS-as-CDN.** Firebase Hosting is the
  sole deploy target. GCS is an internal staging bucket only.

## Gotchas + open issues

- **Hebrew tag URLs**: `/tags/<hebrew>/` routes 500 during `nuxt generate`
  on Windows/WSL — the prerender step fails writing Hebrew-named
  directories. Partial fix is in (`encodeURIComponent` both in
  `nuxt.config.ts` and link generation), but tag pages still 500 after a
  full generate. Next fix: Latin slug map (`tag_slugs`) stored in
  `data.json`, or hash each tag into a stable short ID. Do NOT remove
  tag pages — the user explicitly asked for them.
- **Voyage embeddings are optional.** If `VOYAGE_API_KEY` is unset,
  `embeddings.embed()` returns `None` and `related.py` degrades to
  ministry + shared-tag + agent-suggested scoring. Keep that behavior.
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
