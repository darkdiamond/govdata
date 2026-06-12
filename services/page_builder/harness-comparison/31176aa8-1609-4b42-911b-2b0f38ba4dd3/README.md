# Harness comparison — `31176aa8-1609-4b42-911b-2b0f38ba4dd3`

MiniMax-M3 evaluation run #4 (user-picked), captured 2026-06-11. Same
setup as the `27047419-…` run — see that README for methodology and the
cost-attribution caveat.

## Dataset

CKAN `31176aa8-1609-4b42-911b-2b0f38ba4dd3` — *נתונים תקופתיים - תכנית
דירה בהנחה* (Periodic Data — Discounted Apartment Program, Ministry of
Construction and Housing). 2,352 project lotteries 2016–2025, ~162K
housing units, 15.5M registrations, ~131K winners. A wide, story-rich
dataset — tests the "6–10 distinct charts for wide datasets" rule.

## At-a-glance numbers

| Run | iters | elapsed | input/output tokens | computed $ (uncached) | est. billed $ | content.html | sections / charts |
|---|---|---|---|---|---|---|---|
| Sonnet+MA (prod) | not captured | n/a | n/a | n/a | n/a | 23.7 KB | 9 h2 / 5 charts |
| MiniMax-M3 + harness | 27 | 8.1 min | 408K / 35K | $0.16 | **~$0.07** | 29.1 KB | 10 h2 / 8 charts |

## Data validation (2026-06-12) — units-per-city: PROD RIGHT, M3 FABRICATED

The two pages disagree on units per city. Verdict from re-computing
against the full CKAN table (2,352 rows, fetched whole):

- **Prod Sonnet's chart is exactly correct** — its 12-city array matches
  the raw `sum(LotteryHousingUnits) group by LamasName` to the unit
  (אשקלון 10,976 is the true #1, בית שמש 8,491, באר שבע 7,218 …).
- **M3's "15 הערים המובילות" chart is fabricated.** Its values match no
  real aggregation (ראשון לציון claimed 14,065 vs real 5,991; נצרת
  claimed 6,230 vs real 584 — 10× inflated; אשקלון, the true leader,
  demoted to #13 with 3,380). Transcript forensics: the model paginated
  the full table and aggregated **prices** and **years** by city/date —
  it never ran a units-by-city aggregation — and the topCities array
  first appears in the content.html-writing tool call itself. The
  correct values appear nowhere in its transcript. Classic
  plausible-numbers hallucination.
- M3's *other* numbers are exactly right (total 162,563 units, per-year
  breakdown, 15,516,203 subscribers, 131,442 winners — all verified).

Mitigations added (2026-06-12): a CHART-DATA PROVENANCE hard constraint
in `agent/govdata-agent.yaml` (every inline chart array must be
transcribed from printed query output), a no-`smooth: true` rule for
line charts (M3 used spline smoothing on 3 charts — interpolates
unmeasured values), and a static `smooth: true` check in
`agent/skills/check.py` (verified: fails this M3 page).

## Re-run with the provenance rule (`minimax-m3-v2/`, 2026-06-12)

After adding the CHART-DATA PROVENANCE + no-spline rules, the dataset
was re-run (27 iters, 5.8 min, 410K/22K tokens, ~$0.06 est. billed; one
`finish_reason: "error"` API failure before the clean run — tally now
3 hard failures in 8 sessions). **Every chart array on the new page
validated against the full CKAN table:**

| Chart | Verdict |
|---|---|
| Units + winners by year (combo) | exact match |
| 15 cities by lottery count | exact (עכו/ראש העין tie at 51 — either is right) |
| Mean ₪/m² by year | exact match |
| Subscribers-per-winner ratio by year | exact; formula printed in script |
| Project-status donut (1,154/1,087/109) | exact match |
| Top-10 most competitive lotteries | all 10 are real rows |
| Registration-series donut (12.86M/2.03M/1.6M/0.87M) | exact match |

The provenance discipline visibly changed behavior: instead of a
units-per-city chart it never aggregated (the v1 fabrication), v2
charts lottery *counts* per city — which its script actually printed —
and every inline array string-matches pre-write tool output in the
transcript. Zero `smooth: true`; check.py passed first try
(`OK timeseries`).

Remaining quibbles (wording, not data): one heading says "פרויקטים"
where the data counts הגרלות (the aria-label is correct); the top-10
chart's aria says "מספר הנרשמים הגבוה ביותר" but the selection is
per-unit competitiveness (the raw-subscriber leaders are the רמת גן
44K-registrant lotteries, which have 66–110 units).

## Findings (v1 run, 2026-06-11)

- **Richest M3 output so far** — 8 distinct ECharts (supply/demand
  combo, demand-per-unit ratio line, price-per-m² with semantically
  marked years, two competitiveness rankings, geographic price gap,
  top-15 cities, project-status donut) vs prod's 5. Each tells a
  distinct story; the depth matches the dataset, not padding.
- **Kinds agree** (`timeseries` both). Summary numbers are grounded
  (2,352 / 162,563 / 15.52M / 131,442 all appear in the transcript's
  aggregation outputs).
- **Self-check passed first try** (`OK timeseries`) — first run of the
  four with no check.py iteration loop needed.
- **Reliability strike again**: the FIRST attempt of this dataset died
  mid-session — MiniMax returned HTTP 200 with `finish_reason: "error"`
  (a non-standard value the OpenAI SDK schema rejects; server-side
  generation error). Retry ran clean. Running tally: 2 hard failures in
  6 sessions, two distinct failure modes (malformed tool-call JSON
  here-to-fore, now `finish_reason: error`). A production wrapper needs
  retry-on-failure for both.
- **Render check (Playwright)**: all 8 charts draw, zero agent-code
  script errors.
- Prod's "עיון בהגרלות" section is old-prompt-era hand-built browsing —
  correctly absent from M3's output (the shell explorer owns that now).
