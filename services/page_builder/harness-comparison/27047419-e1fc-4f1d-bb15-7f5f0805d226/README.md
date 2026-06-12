# Harness comparison — `27047419-e1fc-4f1d-bb15-7f5f0805d226`

MiniMax-M3 evaluation run, captured 2026-06-11. First run of the
post-explorer-era system prompt (regenerated from `govdata-agent.yaml`
@ f24e392) through the local harness, and the first run with the
self-check script (`check.py`) provisioned into the Podman sandbox.

## Dataset

CKAN `27047419-e1fc-4f1d-bb15-7f5f0805d226` — *תחנות תחבורה ציבורית*
(Public Transport Stations, Ministry of Transport). ~33.9K stations
with WGS84 coordinates, metropolitan/city/statistical-area assignment,
station type and operator type. `dataset_kind: map` — exercises GovMap,
clustered Leaflet, and categorical ECharts.

## What's where

```
prod-sonnet-managed-agents/   Sonnet 4.6 via Anthropic Managed Agents (production)
                               fetched from https://govil.ai/datasets/<id>/* on 2026-06-11
                               (built when total was 33,911; older prompt era)
minimax-m3/                   MiniMax-M3 via the local harness (api.minimax.io,
                               OpenAI-compat endpoint), 2026-06-11
```

Each directory contains `content.html`, `agent_data.json`, and a
full-page `screenshot.jpeg`. The harness run additionally has
`preview.html` (body spliced into the live shell), `cost.json`, and
`transcript.json`.

## At-a-glance numbers

| Run | iters | elapsed | input/output tokens | cache hit | total $ | content.html | sections |
|---|---|---|---|---|---|---|---|
| Sonnet+MA (prod) | not captured | n/a | n/a | ~95% | n/a (≈$0.50–0.80 typical) | 14.0 KB | 8 h2 |
| MiniMax-M3 + harness | 34 | 7.9 min | 550K / 26K | ~88% (server-side, inferred from billing) | **$0.08 (billed)** | 18.4 KB | 8 h2 |

The checked-in `cost.json` says $0.458 — ignore it. It was computed
with pre-correction list prices AND `cache_read_tokens=0`, because
MiniMax's OpenAI-compat endpoint doesn't report cache fields in the
usage object. Actual platform billing for this run was **$0.08**, which
back-solves to ~480K of the 550K input tokens (~88%) billed at the
$0.06/M cache-read rate — MiniMax caches server-side regardless of what
the usage object claims. Real prices (≤512K tier, permanent 50% off):
$0.30/M input, $1.20/M output, $0.06/M cache read.

Tool calls (MiniMax): 17 bash, 0 code_execution, 0 web_fetch,
0 web_search. It did everything through curl + python3 heredocs in
bash, exactly like the prompt's WORKFLOW prescribes.

## Findings

**Structural parity.** Both pages have 8 sections, 4 ECharts, 1 GovMap,
and a 4-card KPI grid. MiniMax actually exceeds prod on the newer
contract requirements: 4 `<details>` data-table fallbacks (prod: 0) and
5 ARIA labels on viz containers (prod: 1) — though that mostly reflects
the prompt era each ran under, not model capability.

**Numbers are real and internally consistent.** Every distribution in
the MiniMax body sums exactly to the 33,937 total (metro: 12,974 +
10,517 + 4,288 + 4,182 + 1,659 + 317; operators: 33,367 + 295 + 184 +
76 + 15). KPI percentages check out (32,234/33,937 = 95.0%;
12,974/33,937 = 38.2%). The headline insight — 38% of stations lack a
metropolitan assignment — is the same one prod Sonnet found, and both
mark it semantically (red bar / danger KPI).

**Chart judgment.** MiniMax chose a horizontal bar for the operator
distribution; prod used a donut, which at 98.3%-one-slice is arguably
the weaker choice. Otherwise the chart selections are equivalent.

**Self-check loop worked.** First `check.py` run failed (exit 4,
geresh-trap: Hebrew unit abbreviation inside a same-quoted JS string).
The model read the diagnostic, fixed the literal, re-ran, got `OK map`,
and stopped — exactly the intended termination behavior. It also spent
3 iterations reading check.py's source before writing output files
(unprompted; mildly wasteful, mildly clever).

**Render check (Playwright, 2026-06-11).** preview.html loads with zero
script errors from the agent's code; map clusters and all 4 charts draw
with `GOVIL_PALETTE`. Sanitizer fired zero warnings on the body.

**Quibbles.** A couple of slightly-off Hebrew word choices ("הקלדה על
אשכול" where "לחיצה" is meant; "עומדים על תחנה בודדת" is awkward).
`agent_data.json` emitted two null fields not in the schema
(`temporal_coverage`, `spatial_coverage`) — pydantic ignores them, but
it's a small contract drift. `suggested_tags` use hyphenated forms
(`תחנות-אוטובוס`) where prod uses spaced forms (`תחבורה ציבורית`) —
worth normalizing if M3 is adopted.

**Cost.** $0.08/page actually billed (see the caveat under the table) —
roughly 6–10× cheaper than the prod Sonnet+MA path. Caching happens
server-side automatically; the only gap is observability (the compat
endpoint's usage object hides it, so the harness can't attribute it).

## How this was produced

```sh
pip install -r services/page_builder/requirements.txt \
            -r services/page_builder/requirements-test.txt
python -m services.page_builder._build_kimi_system   # regenerate from current yaml

MINIMAX_API_KEY=... python -m services.page_builder.cli.kimi_test \
  --source 27047419-e1fc-4f1d-bb15-7f5f0805d226 --model MiniMax-M3 -v
python -m services.page_builder.cli.preview render 27047419-e1fc-4f1d-bb15-7f5f0805d226
```

## Qwen 3.7 Plus run (`qwen3.7-plus/`, 2026-06-12)

13 iters, 4.3 min, 152K/14K tokens, **$0.0413 actual billed** (OpenRouter).
`OK map` first try, kind agrees (`map`), zero splines, and the provenance
rule held: all chart values trace to printed query output (one derived
value, 13,291 = 12,974+317, merges the two unassigned-metro categories —
legitimate arithmetic, arguably cleaner than two bars).

**But two data errors from one silently-truncated query**: its script ran
`distinct=true&limit=500` on CityName, got exactly 500 rows (the cap),
and (a) shipped a "500 יישובים" KPI — the true count is 1,199; (b)
aggregated top cities over that truncated, roughly-alphabetical list, so
**תל אביב-יפו (true #3, 1,100 stations) is missing from the top-10
chart** (ת sorts last). Everything it did count matches ground truth
exactly. Provenance prevents fabrication, not bad upstream queries —
the distinct-cap trap got an explicit prompt rule after this run.
Body is much leaner than M3/prod (9.4 KB, 3 charts + map, donut for
station types).
