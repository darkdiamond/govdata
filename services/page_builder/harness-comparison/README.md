# Harness comparison snapshots

Reference outputs from running the manual-run model harness
(`services/page_builder/cli/model_test.py`) against representative
datasets. Each subdirectory is one dataset, with one folder per model
that produced output for it, plus a `prod-sonnet-managed-agents/` snapshot
taken from the live govil.ai page so you can compare harness output
against what's actually deployed.

These are checked-in, not gitignored — the point is to have a stable
reference set you can browse months later when re-evaluating a model.
They are NOT regenerated automatically; if you re-run a model, copy the
new artifacts in by hand and update the dataset's `README.md` table.

## Datasets

| Dataset ID | Title | Kind | Notes |
|---|---|---|---|
| `5b0e69e0-b394-4679-9947-b5962d97e718` | התכנית הלאומית למדדי איכות בבריאות הנפש | timeseries | 9 indicators × ~20 institutions × 2014–2024. Mid-sized; good for body density + chart-quality comparison. |
| `27047419-e1fc-4f1d-bb15-7f5f0805d226` | תחנות תחבורה ציבורית | map | ~34K stations with WGS84 coords. Exercises GovMap + categorical charts. MiniMax-M3 eval (2026-06-11), post-explorer prompt + sandboxed check.py. |
| `2b2882aa-5258-4ef4-bcb2-9747dbb62890` | נתון אחרון - איכות מים בקידוחים | timeseries (prod) / registry (M3) | ~60K latest readings × 62 params × 4.1K drillings. MiniMax-M3 eval #2 — analytical depth + a dataset_kind disagreement. |
| `33b03ff6-a58e-49bf-840e-a17a894c9885` | מעבדות אסבסט | registry | 9 labs — thin-registry restraint test. MiniMax-M3 eval #3; first attempt hit a MiniMax 400 (malformed tool-call JSON), retry clean. |
| `31176aa8-1609-4b42-911b-2b0f38ba4dd3` | נתונים תקופתיים - תכנית דירה בהנחה | timeseries | 2,352 lotteries 2016–2025 — wide-dataset depth test (M3: 8 charts vs prod 5). Eval #4; first attempt died on `finish_reason: "error"`, retry clean. |

## Adding a new comparison

```sh
# 1. run the model through the harness
python -m services.page_builder.cli.model_test --source <id> --model <model>

# 2. render the offline preview
python -m services.page_builder.cli.preview render <id>

# 3. copy artifacts into a model-specific subdirectory
mkdir -p services/page_builder/harness-comparison/<id>/<model>/
cp tmp/model_test/<id>/{content.html,agent_data.json,cost.json,transcript.json,preview.html} \
   services/page_builder/harness-comparison/<id>/<model>/

# 4. for the prod-sonnet-managed-agents snapshot, fetch from the live site:
mkdir -p services/page_builder/harness-comparison/<id>/prod-sonnet-managed-agents/
for f in content.html agent_data.json data.json; do
  curl -fsSL https://govil.ai/datasets/<id>/$f \
       -o services/page_builder/harness-comparison/<id>/prod-sonnet-managed-agents/$f
done

# 5. update the per-dataset README.md with the run's stats
```

The harness tool surface (bash + code_execution + web_fetch + web_search)
is **narrower** than Managed Agents (which adds first-class `read`,
`write`, `edit`, `glob`, `grep`). For "model A vs model B" comparisons
on the same harness this is fine; for "harness vs MA" comparisons,
include both prod-sonnet-managed-agents/ and a Sonnet+harness run so
the platform delta is isolated from the model delta.
