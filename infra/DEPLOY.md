# Deployment

Four one-time setups, then the runtime flow is: Cloud Scheduler → Cloud Run
builder (scan CKAN → one Managed Agents session → stage to GCS) → Cloud Build
publisher (generate Nuxt site → deploy to Firebase Hosting).

Container count is pinned to **one** (`--max-instances=1 --concurrency=1`).
Per-source parallelism lives inside that container via `asyncio.gather`;
scale by bumping `N_PER_RUN`, not instance count.

## 1. Project bootstrap — `infra/bootstrap.sh`

Creates the Firebase project (GCP project with the same ID is created
automatically), enables APIs, provisions Firestore + the GCS staging bucket
(with a 30-day age-based lifecycle policy from `infra/staging-lifecycle.json`),
creates the three service accounts, and reserves the Secret Manager secret.

Re-running `bootstrap.sh` re-applies the lifecycle policy. To tweak the
retention window without a full bootstrap:

```sh
gcloud storage buckets update gs://govdata-il-staging \
  --lifecycle-file=infra/staging-lifecycle.json --project=govdata-il
```

Prereqs:

- `firebase login` (interactive, one-time)
- `gcloud auth login` (interactive, one-time)

```sh
bash infra/bootstrap.sh
# populate the Anthropic API key secret
printf '%s' "$ANTHROPIC_API_KEY" \
  | gcloud secrets versions add anthropic-api-key --data-file=- --project=govdata-il
```

The script prints the service account emails it created and ends with
instructions for registering the Cloud Build trigger (needs a connected
repo — either a GitHub 2nd-gen connection or a Cloud Source Repositories
mirror).

## 2. Managed Agent — `infra/setup-agent.sh`

Unchanged from the previous architecture.

Prereqs:

- `ANTHROPIC_API_KEY` exported
- [`ant` CLI](https://platform.claude.com/docs/en/api/sdks/cli.md) on `$PATH`

```sh
bash infra/setup-agent.sh
```

Writes `ANTHROPIC_AGENT_ID` + `ANTHROPIC_ENV_ID` to stdout; export them
before running `builder.deploy.sh`.

## 3. Cloud Run builder — `infra/builder.deploy.sh`

Builds the Docker image from the repo root and deploys the service.

```sh
export ANTHROPIC_AGENT_ID=... ANTHROPIC_ENV_ID=...
bash infra/builder.deploy.sh
```

Notable flags (see script for the full list):

| Flag                | Value                                    |
| ------------------- | ---------------------------------------- |
| `--max-instances`   | 1 (never more than one container)        |
| `--concurrency`     | 1 (one request in flight; no queueing)   |
| `--cpu / --memory`  | 2 / 1Gi (bump memory if `N_PER_RUN > 20`)|
| `--timeout`         | 3600 s (Managed Agents decide when done) |
| `--no-allow-unauthenticated` | Scheduler SA + your own ID token only |

Manual smoke after deploy:

```sh
URL=$(gcloud run services describe govdata-builder --region=me-west1 --format='value(status.url)')
TOKEN=$(gcloud auth print-identity-token)

# Dry run: scan + select but don't fire the agent.
curl -X POST "$URL" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true}'

# Full run on a specific dataset (bypass selector).
curl -X POST "$URL" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"dataset_id": "<ckan-id>"}'
```

## 4. Cloud Scheduler — `infra/scheduler.setup.sh`

Creates the scheduler job **PAUSED**. Enable it only after the manual
invokes have produced real pages.

```sh
bash infra/scheduler.setup.sh
# ... when ready to flip on:
gcloud scheduler jobs resume govdata-pipeline-6h --location=me-west1
```

## Cloud Build publisher trigger

`cloudbuild-publish.yaml` in the repo root contains the full pipeline
(rsync agent artifacts → build manifest from Firestore → `nuxt generate`
+ `firebase deploy --only hosting` in one step). The trigger must be
registered against a connected repo; `infra/bootstrap.sh` prints the
exact `gcloud builds triggers create manual …` invocation after printing
the connection options.

Once registered, the builder fires the trigger at the end of every
successful run via `services/page_builder/pipeline.py::_trigger_publish`.

### Pre-baked publisher image

Every publish step runs on a pre-baked image built by
`cloudbuild-publisher-image.yaml` (Dockerfile at `infra/Dockerfile.publisher`).
The image carries:

- node 22 + a warm npm cache
- `frontend/node_modules` under `/opt/frontend-deps/` so `npm ci` is skipped
  on the fast path (falls back to `npm ci --prefer-offline` if
  `package-lock.json` has drifted from the image)
- python 3.12 + the `services/page_builder/requirements.txt` deps
- the Google Cloud SDK (provides `gsutil` for the rsync step)
- `firebase-tools` globally

Registered as a second Cloud Build trigger path-filtered to
`infra/Dockerfile.publisher`, `frontend/package-lock.json`, and
`services/page_builder/requirements.txt` — so the image only rebuilds when
something it bundles actually changes. `infra/bootstrap.sh` prints the
exact registration command alongside the publish-trigger command, plus a
`gcloud builds triggers run` invocation to populate the `:latest` tag the
first time.

If you change `package-lock.json` or `requirements.txt` and merge before
the image trigger fires, the publish build detects the drift and falls
back to running `npm ci` inline — correct but slower; trigger a rebuild
of the publisher image to restore the fast path.

## Local development

```sh
# Firestore emulator
gcloud emulators firestore start --host-port=localhost:8080 &
export FIRESTORE_EMULATOR_HOST=localhost:8080 FIRESTORE_PROJECT_ID=local-dev

# Seed a few sources
python -m services.scanner.main scan --limit 5

# Dry run the pipeline against the emulator
python -m services.page_builder.pipeline --dry-run

# Full pipeline for one source (needs ANTHROPIC_* + GCS_STAGING_BUCKET if running for real)
python -m services.page_builder.pipeline --source <ckan-id> --no-trigger-publish
```

## Archiving agent output into git

The publisher rsyncs `gs://govdata-il-staging/datasets/` into the Cloud
Build workspace on every deploy, so git never sees the generated
pages. To keep a reviewable snapshot in the repo, pull the current
bucket contents into the working tree and commit by hand:

```sh
./infra/sync-datasets.sh            # dry run — shows what would copy
./infra/sync-datasets.sh --apply    # copies gs://.../datasets/ -> frontend/public/datasets/
git status frontend/public/datasets/
# review, then:
git add frontend/public/datasets/ && git commit -m "publish: sync agent output"
```

The script never deletes — pages only ever accumulate, even if
they're later pruned from the staging bucket.
