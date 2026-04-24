#!/usr/bin/env bash
# One-time bootstrap for govdata-il Firebase + GCP project.
#
# Creates the Firebase project (GCP project with the same ID is created
# automatically), enables APIs, provisions Firestore + GCS + IAM service
# accounts, and creates a Cloud Build trigger for the publisher.
#
# Requires:
#   - firebase CLI        (https://firebase.google.com/docs/cli)
#   - gcloud CLI          (https://cloud.google.com/sdk/docs/install)
#   - `firebase login`    (run once interactively before this script)
#   - `gcloud auth login` (run once interactively before this script)
#
# Safe to re-run — each step is idempotent.

set -euo pipefail

PROJECT=${FIREBASE_PROJECT:-govdata-il}
REGION=${REGION:-me-west1}
STAGING_BUCKET=${GCS_STAGING_BUCKET:-${PROJECT}-staging}
TRIGGER_ID=${PUBLISH_TRIGGER_ID:-govdata-publish}
PUBLISH_BRANCH=${PUBLISH_BRANCH:-main}
REPO_NAME=${CSR_REPO_NAME:-govdata-il}

cd "$(dirname "$0")/.."

echo "==> Project: $PROJECT   Region: $REGION"

# ---- 1. Firebase / GCP project ---------------------------------------------
if gcloud projects describe "$PROJECT" --format='value(projectId)' >/dev/null 2>&1; then
  echo "==> GCP project $PROJECT already exists — ensuring Firebase is attached"
  firebase projects:addfirebase "$PROJECT" >/dev/null 2>&1 || true
else
  echo "==> creating Firebase project $PROJECT"
  firebase projects:create "$PROJECT" --display-name "GovData IL"
fi

gcloud config set project "$PROJECT"

# ---- 2. Enable APIs --------------------------------------------------------
echo "==> enabling required APIs"
gcloud services enable \
  firestore.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  cloudscheduler.googleapis.com \
  firebasehosting.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  --project "$PROJECT"

# ---- 3. Firestore (Native mode) --------------------------------------------
if ! gcloud firestore databases describe --project "$PROJECT" >/dev/null 2>&1; then
  echo "==> creating Firestore database (Native, $REGION)"
  gcloud firestore databases create --location="$REGION" --type=firestore-native --project "$PROJECT"
else
  echo "==> Firestore database already exists"
fi

# ---- 4. GCS staging bucket -------------------------------------------------
if ! gcloud storage buckets describe "gs://$STAGING_BUCKET" --project "$PROJECT" >/dev/null 2>&1; then
  echo "==> creating staging bucket gs://$STAGING_BUCKET"
  gcloud storage buckets create "gs://$STAGING_BUCKET" \
    --location="$REGION" \
    --uniform-bucket-level-access \
    --project "$PROJECT"
else
  echo "==> staging bucket gs://$STAGING_BUCKET already exists"
fi

# ---- 5. Service accounts ---------------------------------------------------
create_sa() {
  local name=$1 display=$2
  if ! gcloud iam service-accounts describe "${name}@${PROJECT}.iam.gserviceaccount.com" --project "$PROJECT" >/dev/null 2>&1; then
    echo "==> creating SA ${name}"
    gcloud iam service-accounts create "$name" --display-name "$display" --project "$PROJECT"
  else
    echo "==> SA ${name} already exists"
  fi
}
create_sa "govdata-builder"   "GovData Cloud Run builder"
create_sa "govdata-publisher" "GovData Cloud Build publisher"
create_sa "govdata-scheduler" "GovData Cloud Scheduler caller"

BUILDER_SA="govdata-builder@${PROJECT}.iam.gserviceaccount.com"
PUBLISHER_SA="govdata-publisher@${PROJECT}.iam.gserviceaccount.com"
SCHEDULER_SA="govdata-scheduler@${PROJECT}.iam.gserviceaccount.com"

echo "==> granting IAM roles"
# Builder: Firestore r/w, GCS r/w on staging, invoke Cloud Build, write logs.
for role in roles/datastore.user roles/logging.logWriter roles/cloudbuild.builds.editor; do
  gcloud projects add-iam-policy-binding "$PROJECT" \
    --member="serviceAccount:$BUILDER_SA" --role="$role" --condition=None --quiet >/dev/null
done
gcloud storage buckets add-iam-policy-binding "gs://$STAGING_BUCKET" \
  --member="serviceAccount:$BUILDER_SA" --role=roles/storage.objectAdmin --quiet >/dev/null

# Publisher: read Firestore + staging, deploy Firebase Hosting.
for role in roles/datastore.viewer roles/logging.logWriter roles/firebasehosting.admin; do
  gcloud projects add-iam-policy-binding "$PROJECT" \
    --member="serviceAccount:$PUBLISHER_SA" --role="$role" --condition=None --quiet >/dev/null
done
gcloud storage buckets add-iam-policy-binding "gs://$STAGING_BUCKET" \
  --member="serviceAccount:$PUBLISHER_SA" --role=roles/storage.objectViewer --quiet >/dev/null

# Builder must be able to impersonate the publisher SA to fire the Cloud Build
# trigger (which runs as the publisher).
gcloud iam service-accounts add-iam-policy-binding "$PUBLISHER_SA" \
  --member="serviceAccount:$BUILDER_SA" --role=roles/iam.serviceAccountUser \
  --project "$PROJECT" --quiet >/dev/null

# Scheduler: may invoke the Cloud Run builder.
# (The run.invoker binding is attached to the service after deploy; see builder.deploy.sh.)

# ---- 6. Secret Manager -----------------------------------------------------
if ! gcloud secrets describe anthropic-api-key --project "$PROJECT" >/dev/null 2>&1; then
  echo "==> creating Secret Manager secret 'anthropic-api-key' (empty; populate via: "
  echo "    printf '%s' \"\$ANTHROPIC_API_KEY\" | gcloud secrets versions add anthropic-api-key --data-file=-)"
  gcloud secrets create anthropic-api-key --replication-policy=automatic --project "$PROJECT" >/dev/null
fi
gcloud secrets add-iam-policy-binding anthropic-api-key \
  --member="serviceAccount:$BUILDER_SA" --role=roles/secretmanager.secretAccessor --quiet >/dev/null || true

# ---- 7. Cloud Build trigger (publisher) ------------------------------------
echo "==> Cloud Build trigger '$TRIGGER_ID'"
if ! gcloud builds triggers describe "$TRIGGER_ID" --region=global --project "$PROJECT" >/dev/null 2>&1; then
  echo "    NOTE: this trigger must be connected to the source repo manually."
  echo "          Options:"
  echo "            - GitHub via 2nd-gen connection: gcloud builds triggers create github ..."
  echo "            - Cloud Source Repositories mirror: connect via Console first, then:"
  echo "                gcloud source repos create $REPO_NAME --project $PROJECT"
  echo "                (push your git remote to https://source.developers.google.com/p/$PROJECT/r/$REPO_NAME)"
  echo
  echo "    Once connected, register the trigger with:"
  echo "      gcloud builds triggers create manual \\"
  echo "        --name=$TRIGGER_ID \\"
  echo "        --repo=projects/$PROJECT/locations/global/connections/<CONN>/repositories/<REPO> \\"
  echo "        --build-config=cloudbuild-publish.yaml \\"
  echo "        --branch=$PUBLISH_BRANCH \\"
  echo "        --service-account=projects/$PROJECT/serviceAccounts/$PUBLISHER_SA \\"
  echo "        --project=$PROJECT"
else
  echo "    trigger already configured"
fi

echo
echo "==> Bootstrap done."
echo "    Builder SA:    $BUILDER_SA"
echo "    Publisher SA:  $PUBLISHER_SA"
echo "    Scheduler SA:  $SCHEDULER_SA"
echo "    Staging bucket: gs://$STAGING_BUCKET"
echo
echo "Next: populate the anthropic-api-key secret, then:"
echo "  bash infra/setup-agent.sh     # create the Managed Agent + Env"
echo "  bash infra/builder.deploy.sh  # deploy the Cloud Run builder"
echo "  bash infra/scheduler.setup.sh # create the (paused) scheduler"
