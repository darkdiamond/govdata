#!/usr/bin/env bash
# Re-run the Managed Agent on the 3 currently-published datasets so they
# pick up the new gov.il-aligned tokens (one per dataset_kind).
# Requires ANTHROPIC_API_KEY + ANTHROPIC_AGENT_ID + ANTHROPIC_ENV_ID in env.
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -z "${ANTHROPIC_API_KEY:-}" || -z "${ANTHROPIC_AGENT_ID:-}" || -z "${ANTHROPIC_ENV_ID:-}" ]]; then
  echo "ERROR: ANTHROPIC_API_KEY / ANTHROPIC_AGENT_ID / ANTHROPIC_ENV_ID must be set." >&2
  echo "Set them (e.g. via 'source .env') and re-run." >&2
  exit 1
fi

# One dataset per kind. Override by exporting DATASETS="id1 id2 ..." before
# running — e.g. to re-run only the two non-perfect pages:
#   DATASETS="c5ac01fb-... ebf0005b-..." ./scripts/rerun-for-govil-redesign.sh
if [[ -n "${DATASETS:-}" ]]; then
  # shellcheck disable=SC2206
  DATASETS=( $DATASETS )
else
  DATASETS=(
    "995eb826-c471-4572-8fd3-39d92a3a9603"  # map        — cellular antennas
    "c5ac01fb-c7ef-4e5e-ba81-e9e11c6f7bd9"  # registry   — non-profit orgs
    "ebf0005b-f5fe-4c6c-ab6d-28778167d025"  # timeseries — Dead Sea water level
  )
fi

OUT="${OUT:-/tmp/gd}"
mkdir -p "$OUT"

# Activate the venv if present.
if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

# Run all datasets in parallel. Each invocation creates its own Managed
# Agents session (independent state, independent quota slot). Stdout/stderr
# from each child is prefixed with the dataset ID so interleaving is readable.
# Set PARALLEL=0 to force sequential.
PARALLEL="${PARALLEL:-1}"

pids=()
for id in "${DATASETS[@]}"; do
  short="${id:0:8}"
  logfile="$OUT/${id}.run.log"
  mkdir -p "$OUT"
  echo ">>> Rebuilding $id (log: $logfile)"
  if [[ "$PARALLEL" == "1" ]]; then
    ( python -m services.page_builder.main "$id" --out "$OUT" 2>&1 \
        | sed -u "s/^/[$short] /" | tee "$logfile" ) &
    pids+=( $! )
  else
    python -m services.page_builder.main "$id" --out "$OUT" 2>&1 | tee "$logfile"
  fi
done

if [[ "$PARALLEL" == "1" ]]; then
  fail=0
  for pid in "${pids[@]}"; do
    wait "$pid" || fail=$((fail + 1))
  done
  if (( fail > 0 )); then
    echo "!!! $fail dataset(s) failed — inspect $OUT/*.run.log" >&2
    exit 1
  fi
fi

echo ">>> Regenerating manifest from $OUT"
python -m services.page_builder.manifest --local "$OUT"

echo
echo "Done. Pages under $OUT/<dataset_id>/. Spot-check one in a browser and"
echo "compare side-by-side with https://www.gov.il/he."
