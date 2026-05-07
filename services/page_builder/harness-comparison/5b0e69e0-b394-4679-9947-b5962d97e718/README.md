# Harness comparison — `5b0e69e0-b394-4679-9947-b5962d97e718`

Reference snapshots from running the same dataset through four different
agent paths, captured 2026-05-06 → 2026-05-07. Use these as the canonical
A/B for "is the harness a faithful proxy of Managed Agents?" and "how
much of the quality gap is the model vs. the agent platform?".

## Dataset

CKAN `5b0e69e0-b394-4679-9947-b5962d97e718` —
*התכנית הלאומית למדדי איכות בבריאות הנפש* (National Program for Mental
Health Quality Indicators). 9 clinical indicators across ~20 health
institutions, time series 2014–2024. Mid-sized timeseries — interesting
enough to exercise charts, big enough to expose differences in agent
investigation depth.

## What's where

```
prod-sonnet-managed-agents/    Sonnet 4.6 via Anthropic Managed Agents (production)
                                fetched from https://govil.ai/datasets/<id>/* on 2026-05-07
kimi-k2.6/                     Kimi K2.6 via the local harness (Moonshot endpoint)
grok-4.3/                      Grok 4.3 via the local harness (xAI endpoint)
anthropic-claude-sonnet-4-6/   Sonnet 4.6 via the local harness (calibration)
```

Each directory contains:

- `content.html` — agent body fragment (the contract output)
- `agent_data.json` — `summary_he`, `dataset_kind`, `related_ids`
- `preview.html` — body spliced into the live govil.ai shell, ready to
  open via `file://` (same renderer as
  `python -m services.page_builder.cli.preview render <id>`)

Harness runs additionally include:

- `cost.json` — tokens + USD breakdown per model + tool-call counters
- `transcript.json` — full PydanticAI message log for that run

(`prod-sonnet-managed-agents/` doesn't have cost or transcript — those
live in the production session_runner logs and weren't captured here.)

## At-a-glance numbers

| Run | iters | elapsed | input/output tokens | cache hit | total $ | content.html size | sections |
|---|---|---|---|---|---|---|---|
| Sonnet+MA (prod) | not captured | n/a | n/a | ~95% | n/a | 23 KB | densest |
| Sonnet+harness | 72 | 6.9 min | 1.46M / 31K | 0% (harness doesn't surface Anthropic cache) | **$4.83** | 18 KB | dense (8 h2) |
| Kimi K2.6 + harness | 84 | 20.7 min | 2.18M / 51K | 96% | $0.49 | 14 KB | rich (per prior run) |
| Grok 4.3 + harness | 20 | 1.1 min | 179K / 3K | 0% (xAI compat doesn't expose) | $0.23 | 6 KB | thin (4 h2) |

**Key calibration finding** (Sonnet+MA vs Sonnet+harness):
The same model produces comparable structural depth (Sonnet+MA: 23 KB,
Sonnet+harness: 18 KB) when given the same prompt, even with the harness's
narrower tool surface. The cost gap (10× the price of Kimi+harness) is
entirely explained by the harness not surfacing Anthropic's prompt cache —
1.46M input tokens at full $3/1M rates vs MA's ~95% cache discount. The
loss in body density (5 KB) is the cost of bash-heredoc file-writes
instead of MA's native `write` tool.

**Sonnet vs Kimi vs Grok (same harness)** isolates the model's contribution.
Sonnet picks the most useful insight (89.3% compliance vs 80% target —
real analytical finding) and produces the densest body. Kimi is strong on
investigation depth (84 iters!) and similar in body density. Grok bailed
on data-fetching after one curl failure, producing the thinnest body and
empty `related_ids`.

## Methodology notes

- The prod Sonnet+MA snapshot was fetched live from govil.ai
  (Cloudflare-fronted static files), so it reflects whatever was
  deployed on 2026-05-07. The publish pipeline rebuilds these on every
  Cloud Build trigger, so this is a moment-in-time capture.
- Harness runs all share the same regenerated system prompt
  (`agent/govdata-agent-kimi.system.md`) and the same `build_user_message`
  text. The only knob varied is `--model`.
- Harness tool surface is bash + code_execution + web_fetch + web_search.
  Managed Agents adds `read`, `write`, `edit`, `glob`, `grep` as
  first-class tools; in the harness the agent does file I/O via bash
  heredocs and `sed -i`. This is the load-bearing structural difference
  — the Sonnet+harness run isolates how much of the quality gap is the
  model vs the harness's missing tools.
- The Sonnet+harness run required `pydantic-ai >= 1.91.0` and an
  explicit `max_tokens=16384` on the Agent. Earlier runs on
  pydantic-ai 1.89.1 with the default `max_tokens` (~4096) failed:
  Sonnet's bash heredocs (multi-KB python scripts) blew the token
  ceiling mid-stream and the Anthropic streaming adapter dropped the
  tool_use input arguments, leaving `input={}`. PydanticAI's loop saw
  this as repeated empty tool calls and raised `UnexpectedModelBehavior`
  after retries=5. Tracked in pydantic-ai #3118 / PR #3137.

## How these were produced

```sh
pip install -r services/page_builder/requirements.txt \
            -r services/page_builder/requirements-test.txt
python -m services.page_builder._build_kimi_system

# the three harness runs:
python -m services.page_builder.cli.kimi_test --source <id> --model kimi-k2.6
python -m services.page_builder.cli.kimi_test --source <id> --model grok-4.3
python -m services.page_builder.cli.kimi_test --source <id> --model anthropic:claude-sonnet-4-6

# preview render produces preview.html:
python -m services.page_builder.cli.preview render <id>
```

## How to view side-by-side

Open the four `preview.html` files in adjacent browser tabs. Each is a
self-contained snapshot of how the body would render through the live
prod shell (Tailwind, dataset-libs globals, related-datasets sidebar
all loaded from `https://govil.ai/...` via Cloudflare).

The sidebar / metadata cards / SEO meta in each preview reflect prod
state — only the agent body is swapped.
