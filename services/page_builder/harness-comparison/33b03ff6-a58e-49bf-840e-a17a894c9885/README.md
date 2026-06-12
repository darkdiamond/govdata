# Harness comparison — `33b03ff6-a58e-49bf-840e-a17a894c9885`

MiniMax-M3 evaluation run #3 (registry kind, small dataset), captured
2026-06-11. Same setup as the `27047419-…` run — see that README for
methodology and the cost-attribution caveat.

## Dataset

CKAN `33b03ff6-a58e-49bf-840e-a17a894c9885` — *מעבדות אסבסט* (Asbestos
Laboratories, Ministry of Environmental Protection). 9 licensed labs —
a deliberately thin registry that tests restraint: does the model stop
at 2 charts, or pad?

## At-a-glance numbers

| Run | iters | elapsed | input/output tokens | computed $ (uncached) | est. billed $ | content.html | sections |
|---|---|---|---|---|---|---|---|
| Sonnet+MA (prod) | not captured | n/a | n/a | n/a | n/a | 13.5 KB | 6 h2 |
| MiniMax-M3 + harness | 17 | 3.0 min | 190K / 14K | $0.07 | **~$0.03** | 15.7 KB | 5 h2 |

## Findings

- **Right-sized restraint**: 2 charts (license type, expiry year — with
  an amber bar marking the one license expiring in 2026), 4 KPIs, and a
  hand-curated 9-row table of all labs with disciplinary-note badges.
  Same shape as prod. No padding.
- **Kinds agree** (`registry` both).
- **First attempt of this dataset failed** with a MiniMax API 400:
  the model emitted a tool call with malformed JSON arguments, and the
  API then rejected its own tool call when the history was replayed
  ("invalid function arguments json string"). The retry ran clean.
  Failure rate so far: 1 in 4 sessions — needs a retry wrapper if M3
  ever goes near production.
- **Self-check**: passed (`OK registry` verified locally); sanitizer
  fired nothing. Render check (Playwright): both charts draw, zero
  agent-code script errors.

## Qwen 3.7 Plus run (`qwen3.7-plus/`, 2026-06-12)

17 iters, 3.1 min, 201K/10K tokens, **$0.0402 actual billed** (OpenRouter).
`OK registry` first try; KPIs check out (9 labs, 7 without disciplinary
notes, 5 sampling / 4 analysis permits). Thinnest output of the three
models (4.7 KB, 2 charts, no curated all-labs table, no `<details>`
fallbacks) — passes the contract but skips the lab-roster table both M3
and prod judged worth shipping for a 9-row registry.
