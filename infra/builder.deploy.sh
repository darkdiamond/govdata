#!/usr/bin/env bash
# Deploy the govdata-builder Cloud Run service.
#
# Single container, pinned to one instance, concurrency=1. Parallelism across
# sources lives entirely in asyncio.gather inside the container — see
# services/page_builder/pipeline.py.
#
# Requires:
#   - infra/bootstrap.sh already run (project, SAs, staging bucket exist)
#   - infra/setup-agent.sh already run (agent + env IDs captured below)

set -euo pipefail

PROJECT=${FIREBASE_PROJECT:-govdata-il}
REGION=${REGION:-me-west1}
SERVICE=${CLOUD_RUN_SERVICE:-govdata-builder}
STAGING_BUCKET=${GCS_STAGING_BUCKET:-${PROJECT}-staging}
TRIGGER_ID=${PUBLISH_TRIGGER_ID:-govdata-publish}
PUBLISH_BRANCH=${PUBLISH_BRANCH:-main}
N_PER_RUN=${N_PER_RUN:-2}
SCAN_LIMIT=${SCAN_LIMIT:-500}

: "${ANTHROPIC_AGENT_ID:?set ANTHROPIC_AGENT_ID (from infra/setup-agent.sh)}"
: "${ANTHROPIC_ENV_ID:?set ANTHROPIC_ENV_ID (from infra/setup-agent.sh)}"

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
  --set-env-vars="FIRESTORE_PROJECT_ID=${PROJECT},GOOGLE_CLOUD_PROJECT=${PROJECT},FIREBASE_PROJECT=${PROJECT},GCS_STAGING_BUCKET=${STAGING_BUCKET},PUBLISH_TRIGGER_ID=${TRIGGER_ID},PUBLISH_BRANCH=${PUBLISH_BRANCH},N_PER_RUN=${N_PER_RUN},SCAN_LIMIT=${SCAN_LIMIT},ANTHROPIC_AGENT_ID=${ANTHROPIC_AGENT_ID},ANTHROPIC_ENV_ID=${ANTHROPIC_ENV_ID}" \
  --set-secrets="ANTHROPIC_API_KEY=anthropic-api-key:latest,VOYAGE_API_KEY=voyage-api-key:latest" \
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
