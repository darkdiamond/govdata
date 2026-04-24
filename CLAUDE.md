# CLAUDE.md — repository conventions for Claude Code sessions

This file is loaded automatically. Read it before touching code.

## What this project is

A pipeline that turns data.gov.il datasets into connected, Hebrew-RTL
landing pages. The architecture lives in four layers:

1. **Scanner** — `services/scanner/` (existing, stable). Polls CKAN, tracks
   change state in SQLite, fires webhooks via `ScanCallbacks` /
   `HttpWebhookCallbacks`.
2. **Controller** — `services/page_builder/`. A GCP Cloud Function. One HTTP
   invocation per dataset: creates a Managed Agents session, streams until
   idle, downloads outputs, wraps + publishes.
3. **Managed Agent** — `agent/*.yaml` + `agent/skills/`. Anthropic-hosted,
   `claude-sonnet-4-6` in a per-session container. Writes `content.html`
   (body) + `data.json` (manifest entry). Allowed to use bash, web_search,
   web_fetch, code_execution, file writing.
4. **Frontend** — `frontend/`. Nuxt 3 SSG for home + category pages only.
   Per-dataset pages are agent-authored HTML served directly from the CDN.

## Critical conventions

- **Hebrew-first, RTL everywhere.** `<html dir="rtl" lang="he">`. Body
  line-height 1.7. Tailwind logical properties (`ps-*`/`pe-*`) when using
  Tailwind.
- **Model**: `claude-sonnet-4-6`. The user explicitly chose this; do not
  upgrade to Opus without asking. If adding new Claude calls, follow the
  `claude-api` skill: adaptive thinking, prompt caching, no `budget_tokens`,
  no `temperature`/`top_p`/`top_k` on 4.6+.
- **Design tokens** (match `agent/skills/govdata-design/SKILL.md`):
  primary `#0B3D91`, accent `#EAB308`, surface `#FAFAF7`, ink `#111`,
  subtle `#6B7280`, rule `#E5E7EB`. Fonts: Heebo (body), Rubik (display).
- **Agent outputs** are a contract:
  - `/mnt/session/outputs/content.html` — body content only. No
    `<html>`/`<head>`/`<body>`. Inline `<style>` and `<script>` tags OK.
  - `/mnt/session/outputs/data.json` — a `ManifestEntry` (see
    `services/page_builder/schema.py`).
- **Manifest is the single source of truth** for what the home/category
  pages show. It's rebuilt after every session from all per-dataset
  `data.json` files.
- **Related-datasets scoring** is deterministic:
  `5·same_ministry + 2·min(shared_tag_count, 6) + 3·cosine(embedding) + 4·agent_suggested`.
  Top 5 per page. Defined in `services/page_builder/related.py`.

## Key files to read before editing

| Area | File | Why |
|------|------|-----|
| Agent behavior | `agent/govdata-agent.yaml` | The agent's Hebrew system prompt — full workflow + constraints |
| Agent design | `agent/skills/govdata-design/SKILL.md` | Design tokens + output-file contract |
| Session orchestration | `services/page_builder/session_runner.py` | Stream-first, terminal-idle gate, enrichment, wrap, publish |
| Page chrome | `services/page_builder/templates/dataset_page.html.j2` | What every dataset page shares (header, breadcrumb, related, footer) |
| Schema | `services/page_builder/schema.py` | `ManifestEntry` — the boundary between agent + controller + frontend |
| Routing | `frontend/nuxt.config.ts` | Enumerates prerender routes from the manifest |

## Conventions you will be tempted to violate (don't)

- **Don't add LLM fallbacks or mock analyzers.** The user explicitly asked
  to remove these earlier — production must use Managed Agents.
- **Don't resurrect the viz taxonomy.** The agent picks libraries per
  dataset. Any code that hardcodes `VizType` / `VizSpec` is obsolete.
- **Don't add a Nuxt route for `/datasets/[id]`.** Dataset pages are
  agent-authored HTML served by the CDN outside Nuxt. Category routes
  (`/ministries/[slug]`, `/tags/[slug]`, `/kinds/[kind]`) are the only
  dynamic ones Nuxt owns.
- **Don't set client-side wall-clock timeouts** on the agent session. The
  user wants the agent to decide when it's done. Only the GCP function
  timeout (3600 s) bounds it.
- **Don't push to `main` without asking.** Commits yes; pushes require
  explicit branch confirmation.

## Gotchas + open issues

- **Hebrew tag URLs**: `/tags/<hebrew>/` routes 500 during `nuxt generate`
  on Windows/WSL — the prerender step appears to fail writing Hebrew-named
  directories. Partial fix is in (`encodeURIComponent` in both
  `nuxt.config.ts` and link generation), but tag pages still 500 after a
  full generate. Next fix: use a Latin slug map stored in `data.json`
  (agent emits `tags_he` + `tag_slugs` pairs), or hash each tag into a
  stable short ID. Do NOT remove tag pages — the user explicitly asked for
  them.
- **Voyage embeddings are optional.** If `VOYAGE_API_KEY` is unset,
  `embeddings.embed()` returns `None` and `related.py` degrades to
  ministry + shared-tag + agent-suggested scoring. Keep that behavior.
- **Plan file vs reality**: `/home/zilbert/.claude/plans/i-m-building-a-website-cryptic-crown.md`
  reflects the Managed Agents architecture. If the plan drifts from the
  code again, update it.
- **Anthropic SDK**: minimum `0.92.0` for `client.beta.files.list(scope_id=...)` —
  older versions reject the parameter.

## Running things locally

```sh
# Tests + imports
source venv/bin/activate
python -c "from services.page_builder.main import build; print('ok')"

# Scanner dry run (no webhook)
python -m services.scanner.main scan --limit 3 --no-download

# One-dataset build (requires ANTHROPIC_API_KEY + AGENT_ID + ENV_ID)
python -m services.page_builder.main <dataset_id> --out /tmp/gd

# Aggregate manifest from a local tree
python -m services.page_builder.manifest --local /tmp/gd

# Frontend
cd frontend && npm run generate && npx serve .output/public
```

## Memory

Feedback memories are under `~/.claude/projects/-mnt-d-workdir-govdata/memory/`:
- `plan_mode_tooling.md` — running the scanner during plan mode is OK.

When the user gives feedback that changes approach (e.g., "only keep the
agent analyzer", "ship via Managed Agents"), save it as a feedback memory
so future sessions don't re-litigate.
