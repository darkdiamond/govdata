# Contributing to govil.ai

Thanks for your interest in contributing! This project turns
[data.gov.il](https://data.gov.il) datasets into connected, Hebrew-RTL
landing pages. Contributions of all kinds are welcome — bug reports,
documentation, frontend polish, agent-prompt improvements, and pipeline
features.

Please read this guide and the [Code of Conduct](CODE_OF_CONDUCT.md)
before opening a pull request.

## Architecture first

Before changing pipeline or agent code, skim:

- [`README.md`](README.md) — what the project is and how to run it
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — the four layers
  (scanner → builder → agent runtime → publisher) and the data model
- [`CLAUDE.md`](CLAUDE.md) — detailed repository conventions and the
  "things you'll be tempted to do but shouldn't" list

## Development setup

Prerequisites: Python 3.12, Node 22, and an
[OpenRouter API key](https://openrouter.ai/settings/keys).

```sh
# Python services
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -U pip   # stock pip 24.x fails to resolve pydantic-ai's extras
pip install -r services/page_builder/requirements.txt

# Frontend
cd frontend && npm install

# Local state — run against the Firestore emulator, never production
# (the emulator needs a Java 8+ JRE on PATH)
gcloud emulators firestore start --host-port=localhost:8080 &
export FIRESTORE_EMULATOR_HOST=localhost:8080 FIRESTORE_PROJECT_ID=local-dev
```

Copy [`.env.example`](.env.example) to `.env` and fill in the values you
need. `.env` is gitignored — **never commit secrets**.

See the [README quick start](README.md#quick-start) for an end-to-end
local run, and the [model harness](README.md#manual-run-model-harness-any-model-via-openrouter)
section for evaluating agent output without touching the live pipeline.

## Running tests

```sh
source .venv/bin/activate
pytest services/page_builder/tests/ -q
```

The agent self-check (`agent/skills/check.py`) runs both inside each
agent session and host-side during production runs — if you change the
output contract or the system prompt's hard rules, keep the check script
in sync.

For frontend changes, confirm a clean static build:

```sh
cd frontend && npm run generate
```

## Coding conventions

- **Python**: follow PEP 8, use type hints, keep functions focused.
  Match the style of the surrounding module.
- **Frontend**: TypeScript + Vue 3 (Nuxt 3). Match existing component
  patterns.
- **Hebrew-first / RTL**: the UI is `<html dir="rtl" lang="he">`. Respect
  the design tokens documented in `CLAUDE.md` and mirrored across
  `frontend/tailwind.config.ts`, the page template, and
  `agent/system-prompt.md`. Use logical CSS properties (`ps-*`/`pe-*`).
- **Single source of truth**: per-dataset data is materialized from the
  Firestore `sources/<id>` document by the publisher. Don't add code
  paths that write `data.json` / `manifest.json` from anywhere else.

## Commit messages

This repo uses [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(frontend): add tag-cloud to home page
fix(pipeline): retry transient OpenRouter 5xx
docs: clarify self-hosting env vars
```

Common prefixes here: `feat`, `fix`, `perf`, `docs`, `refactor`,
`chore`, `infra`.

## Pull requests

1. Fork the repo and create a topic branch.
2. Make your change with a focused, well-described commit history.
3. Run the tests and (for frontend changes) `npm run generate`.
4. Open a PR using the template — link any related issue and note how
   you verified the change.

Small, focused PRs are reviewed fastest. For larger changes, open an
issue first to discuss the approach.

## Reporting security issues

**Do not open a public issue for security vulnerabilities.** See
[SECURITY.md](SECURITY.md) for private reporting.
