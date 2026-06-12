#!/usr/bin/env bash
# Create the Cloud Scheduler job for govdata-builder. The job is created
# PAUSED — resume it explicitly once the manual invokes look good:
#
#   gcloud scheduler jobs resume govdata-pipeline-6h --location=me-west1
#
# Requires:
#   - infra/bootstrap.sh already run
#   - infra/builder.deploy.sh already run (so the Cloud Run URL exists)

set -euo pipefail

PROJECT=${FIREBASE_PROJECT:-govdata-il}
REGION=${REGION:-me-west1}
SERVICE=${CLOUD_RUN_SERVICE:-govdata-builder}
JOB_NAME=${SCHEDULER_JOB:-govdata-pipeline-daily}
SCHEDULE=${SCHEDULE:-"0 7 * * *"}
TIMEZONE=${SCHEDULE_TZ:-"Asia/Jerusalem"}

SCHEDULER_SA="govdata-scheduler@${PROJECT}.iam.gserviceaccount.com"

URL=$(gcloud run services describe "$SERVICE" \
  --region="$REGION" --project="$PROJECT" --format='value(status.url)')
if [[ -z "$URL" ]]; then
  echo "Cloud Run service $SERVICE not found in $REGION. Deploy it first." >&2
  exit 2
fi

if gcloud scheduler jobs describe "$JOB_NAME" --location="$REGION" --project="$PROJECT" >/dev/null 2>&1; then
  echo "==> updating existing scheduler job $JOB_NAME"
  gcloud scheduler jobs update http "$JOB_NAME" \
    --location="$REGION" \
    --project="$PROJECT" \
    --schedule="$SCHEDULE" \
    --time-zone="$TIMEZONE" \
    --uri="$URL" \
    --http-method=POST \
    --headers="Content-Type=application/json" \
    --message-body='{}' \
    --oidc-service-account-email="$SCHEDULER_SA" \
    --oidc-token-audience="$URL"
else
  echo "==> creating scheduler job $JOB_NAME"
  gcloud scheduler jobs create http "$JOB_NAME" \
    --location="$REGION" \
    --project="$PROJECT" \
    --schedule="$SCHEDULE" \
    --time-zone="$TIMEZONE" \
    --uri="$URL" \
    --http-method=POST \
    --headers="Content-Type=application/json" \
    --message-body='{}' \
    --oidc-service-account-email="$SCHEDULER_SA" \
    --oidc-token-audience="$URL"
fi

echo "==> pausing $JOB_NAME (testing via manual invoke until we flip the switch)"
gcloud scheduler jobs pause "$JOB_NAME" --location="$REGION" --project="$PROJECT"

echo
echo "==> scheduler job ready (paused):"
gcloud scheduler jobs describe "$JOB_NAME" --location="$REGION" --project="$PROJECT" \
  --format="value(name,state,schedule,timeZone)"
echo
echo "Resume later with:"
echo "  gcloud scheduler jobs resume $JOB_NAME --location=$REGION --project=$PROJECT"
