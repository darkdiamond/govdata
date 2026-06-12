#!/usr/bin/env bash
# Deploy the govdata-builder Cloud Run service.
#
# Single container, pinned to one instance, concurrency=1. Parallelism across
# sources lives entirely in asyncio.gather (bounded by MAX_CONCURRENT) inside
# the container — see services/page_builder/pipeline.py. Agent sessions call
# OpenRouter (OPENROUTER_MODEL); switching production model = redeploy with a
# different env var.
#
# Requires:
#   - infra/bootstrap.sh already run (project, SAs, staging bucket exist)
#   - the openrouter-api-key secret created once:
#       gcloud secrets create openrouter-api-key --data-file=<keyfile> --project=<proj>
#       gcloud secrets add-iam-policy-binding openrouter-api-key \
#         --member="serviceAccount:govdata-builder@<proj>.iam.gserviceaccount.com" \
#         --role=roles/secretmanager.secretAccessor --project=<proj>

set -euo pipefail

PROJECT=${FIREBASE_PROJECT:-govdata-il}
REGION=${REGION:-me-west1}
SERVICE=${CLOUD_RUN_SERVICE:-govdata-builder}
STAGING_BUCKET=${GCS_STAGING_BUCKET:-${PROJECT}-staging}
TRIGGER_ID=${PUBLISH_TRIGGER_ID:-govdata-publish}
PUBLISH_BRANCH=${PUBLISH_BRANCH:-main}
OPENROUTER_MODEL=${OPENROUTER_MODEL:-minimax/minimax-m3}
DAILY_CAP=${DAILY_CAP:-50}
MAX_CONCURRENT=${MAX_CONCURRENT:-8}
SESSION_ATTEMPTS=${SESSION_ATTEMPTS:-3}
SCAN_LIMIT=${SCAN_LIMIT:-500}
# Pause Track 2 re-analysis until structural-change gating exists (see
# services/page_builder/selector.py). Flip back with REANALYZE_ENABLED=true.
REANALYZE_ENABLED=${REANALYZE_ENABLED:-false}

cd "$(dirname "$0")/.."

BUILDER_SA="govdata-builder@${PROJECT}.iam.gserviceaccount.com"
SCHEDULER_SA="govdata-scheduler@${PROJECT}.iam.gserviceaccount.com"

echo "==> deploying $SERVICE to Cloud Run ($REGION, project $PROJECT)"
gcloud run deploy "$SERVICE" \
  --source=. \
  --region="$REGION" \
  --service-account="$BUILDER_SA" \
  --cpu=2 \
  --memory=1Gi \
  --max-instances=1 \
  --concurrency=1 \
  --timeout=3600 \
  --no-allow-unauthenticated \
  --set-env-vars="FIRESTORE_PROJECT_ID=${PROJECT},GOOGLE_CLOUD_PROJECT=${PROJECT},FIREBASE_PROJECT=${PROJECT},GCS_STAGING_BUCKET=${STAGING_BUCKET},PUBLISH_TRIGGER_ID=${TRIGGER_ID},PUBLISH_BRANCH=${PUBLISH_BRANCH},OPENROUTER_MODEL=${OPENROUTER_MODEL},DAILY_CAP=${DAILY_CAP},MAX_CONCURRENT=${MAX_CONCURRENT},SESSION_ATTEMPTS=${SESSION_ATTEMPTS},SCAN_LIMIT=${SCAN_LIMIT},REANALYZE_ENABLED=${REANALYZE_ENABLED}" \
  --set-secrets="OPENROUTER_API_KEY=openrouter-api-key:latest,VOYAGE_API_KEY=voyage-api-key:latest" \
  --project="$PROJECT"

echo "==> granting Cloud Scheduler SA permission to invoke this service"
gcloud run services add-iam-policy-binding "$SERVICE" \
  --member="serviceAccount:$SCHEDULER_SA" \
  --role=roles/run.invoker \
  --region="$REGION" \
  --project="$PROJECT" \
  --quiet >/dev/null

URL=$(gcloud run services describe "$SERVICE" --region="$REGION" --project="$PROJECT" --format='value(status.url)')
echo
echo "==> service deployed at: $URL"
echo
echo "Manual test:"
echo "  TOKEN=\$(gcloud auth print-identity-token)"
echo "  curl -X POST \"$URL\" -H \"Authorization: Bearer \$TOKEN\" -H 'Content-Type: application/json' -d '{\"dry_run\": true}'"
