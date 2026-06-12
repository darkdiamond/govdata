# Harness comparison — `2b2882aa-5258-4ef4-bcb2-9747dbb62890`

MiniMax-M3 evaluation run #2 (timeseries-ish kind), captured 2026-06-11.
Same harness setup as the `27047419-…` run (post-explorer prompt,
sandboxed check.py) — see that dataset's README for the methodology and
the cost-attribution caveat.

## Dataset

CKAN `2b2882aa-5258-4ef4-bcb2-9747dbb62890` — *נתון אחרון - איכות מים
בקידוחים* (Latest Reading — Water Quality in Drillings, Water
Authority). ~59.9K latest-measurement rows × 62 parameters × ~4.1K
drillings. Exercises multi-chart analytical depth, exceedance
semantics, and parameter-group aggregation.

## At-a-glance numbers

| Run | iters | elapsed | input/output tokens | computed $ (uncached) | est. billed $ | content.html | sections |
|---|---|---|---|---|---|---|---|
| Sonnet+MA (prod) | not captured | n/a | n/a | n/a | n/a | 16.6 KB | 9 h2 |
| MiniMax-M3 + harness | 30 | 8.4 min | 526K / 26K | $0.19 | **~$0.08** | 22.9 KB | 8 h2 |

(est. billed assumes the ~88% server-side cache rate observed on the
27047419 run; MiniMax's compat endpoint doesn't report cache fields.)

## Findings

- **Denser body than prod** (22.9 KB vs 16.6 KB): 5 ECharts each, but
  M3 adds 5 `<details>` table fallbacks and ARIA labels on every chart.
  Prod's extra section is a hand-built "עיון בנתוני הקידוחים" explorer
  from the pre-shell-explorer prompt era — correctly absent from M3's
  output under the current contract.
- **Kind disagreement worth noting**: prod says `timeseries`, M3 says
  `registry`. M3's call is arguably more faithful to the prompt's rule
  (each row is a *latest* snapshot, not a date axis with ≥3 points) —
  but it means a re-analysis would silently move the page between
  /kinds/ routes.
- **Self-check loop**: first check.py run failed (exit 4), the model
  fixed the body inline and verified; the staged artifact passes
  `OK registry` locally, sanitizer fired nothing.
- **Render check (Playwright)**: all 5 charts draw, zero script errors
  from agent code. Semantic color use is purposeful (red exceedance
  bars, green 2026 sampling-year bar) though the all-red top-10 nitrate
  chart pushes the "semantic, not categorical" rule to its edge.
- **Analytical quality**: insights quantify exceedance leaders (nitrate,
  chloride), name extreme coastal/agricultural drillings, and flag the
  PFAS parameters — all grounded in queries from the transcript.
