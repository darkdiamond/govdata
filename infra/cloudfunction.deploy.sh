#!/usr/bin/env bash
# Deploy the page_builder Cloud Function to GCP.
#
# Prereqs (run once, outside this script):
#   gcloud auth login
#   gcloud config set project <YOUR-PROJECT-ID>
#   gcloud services enable cloudfunctions.googleapis.com secretmanager.googleapis.com storage.googleapis.com
#   gcloud secrets create anthropic-api-key --data-file=- <<< "$ANTHROPIC_API_KEY"
#   gsutil mb -l me-west1 gs://govdata-content   # or your bucket name
#
# Then edit the BUCKET and HOOK vars below and run this script.
set -euo pipefail

REGION="${REGION:-me-west1}"
FUNCTION_NAME="${FUNCTION_NAME:-page-builder}"
BUCKET="${GCS_CONTENT_BUCKET:-govdata-content}"
HOOK_FILE="${HOOK_FILE:-infra/pages.build-hook.txt}"
HOOK_URL="${CLOUDFLARE_BUILD_HOOK:-$(cat "$HOOK_FILE" 2>/dev/null || true)}"

: "${ANTHROPIC_AGENT_ID:?run infra/setup-agent.sh first to create the agent}"
: "${ANTHROPIC_ENV_ID:?run infra/setup-agent.sh first to create the environment}"

if [[ -z "$HOOK_URL" ]]; then
  echo "warning: CLOUDFLARE_BUILD_HOOK unset and $HOOK_FILE missing — deploys will skip build trigger"
fi

cd "$(dirname "$0")/../services/page_builder"

gcloud functions deploy "$FUNCTION_NAME" \
  --gen2 \
  --region="$REGION" \
  --runtime=python312 \
  --trigger-http \
  --no-allow-unauthenticated \
  --memory=1024MB \
  --timeout=3600s \
  --entry-point=http_entry \
  --source=. \
  --set-env-vars="ANTHROPIC_AGENT_ID=$ANTHROPIC_AGENT_ID,ANTHROPIC_ENV_ID=$ANTHROPIC_ENV_ID,GCS_CONTENT_BUCKET=$BUCKET,CLOUDFLARE_BUILD_HOOK=$HOOK_URL" \
  --set-secrets="ANTHROPIC_API_KEY=anthropic-api-key:latest"

echo ""
echo "Deployed. Scanner will reach the function at:"
gcloud functions describe "$FUNCTION_NAME" --region="$REGION" --format="value(serviceConfig.uri)"
