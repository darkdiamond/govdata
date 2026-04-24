# Deployment

Three one-time setups, then the runtime flow is: scanner webhook → Cloud Function
controller → Managed Agents session → CDN publish.

## 1. Managed Agent + Environment (one-time, via `ant` CLI)

Prereqs:

- `ANTHROPIC_API_KEY` exported in your shell
- [`ant` CLI](https://platform.claude.com/docs/en/api/sdks/cli.md) on `$PATH`

```sh
bash infra/setup-agent.sh
```

It prints `ANTHROPIC_AGENT_ID` and `ANTHROPIC_ENV_ID`. Copy both into your
deployment env (Secret Manager, Cloud Function env vars, or local `.env`).

**Updating the agent later** (e.g., system prompt tweaks):
```sh
ant beta:agents update --agent-id "$ANTHROPIC_AGENT_ID" --version <N> < agent/govdata-agent.yaml
```
Each update creates a new version. Sessions pin to the latest unless you pass
`{type: "agent", id, version: N}` explicitly.

## 2. Cloud Function — `services/page_builder`

The controller: one HTTP invocation per dataset, creates a Managed Agents
session, streams until idle, downloads outputs to GCS, fires the build hook.

Prereqs:

- GCP project selected (`gcloud config set project …`)
- APIs enabled: `cloudfunctions`, `secretmanager`, `storage`
- Secret created: `gcloud secrets create anthropic-api-key --data-file=- <<< "$ANTHROPIC_API_KEY"`
- GCS bucket: `gsutil mb -l me-west1 gs://govdata-content`

Edit `infra/cloudfunction.deploy.sh` (bucket name + agent/env IDs), then:

```sh
bash infra/cloudfunction.deploy.sh
```

Runtime env vars the function needs:

| Var                    | Value                                    |
| ---------------------- | ---------------------------------------- |
| `ANTHROPIC_AGENT_ID`   | From step 1                              |
| `ANTHROPIC_ENV_ID`     | From step 1                              |
| `GCS_CONTENT_BUCKET`   | `govdata-content`                        |
| `CLOUDFLARE_BUILD_HOOK`| From step 3                              |
| `ANTHROPIC_API_KEY`    | From Secret Manager (bound at deploy)    |

**Timeout:** set the function timeout to the maximum your deploy target
permits (Cloud Functions Gen 2 allows 3600 s). Agents decide when they're
done; the controller does not impose a wall clock. For datasets that genuinely
exceed 60 minutes, migrate the controller to Cloud Run Jobs.

## 3. Static site — `frontend/` + CDN for agent outputs

**Home page — Cloudflare Pages** (or Firebase Hosting / Netlify):

- Build command: `npm install && npm run generate`
- Output directory: `frontend/.output/public`
- Root directory (advanced): `frontend`
- Prebuild step (sync the manifest from GCS so the home page sees the current dataset list):
  ```sh
  gsutil cp gs://govdata-content/manifest.json frontend/public/data/manifest.json
  ```

After the project is created, copy its **Deploy Hook URL** to:
- `infra/pages.build-hook.txt` (gitignored, for local use), and
- the Cloud Function env var `CLOUDFLARE_BUILD_HOOK` (redeploy the function).

**Dataset pages — direct from GCS** (the agent writes `index.html` per dataset):

- Make `gs://govdata-content/datasets/` publicly readable:
  ```sh
  gsutil iam ch allUsers:objectViewer gs://govdata-content
  ```
- Expose `/datasets/{id}/` on the same origin as the Nuxt site. Two options:
  1. **Cloudflare Pages with an origin rule** routing `/datasets/*` to
     `https://storage.googleapis.com/govdata-content/datasets/*`.
  2. **GCS as a second Pages project** (simpler) with a `datasets.` subdomain.

## 4. Manifest refresh

`manifest.json` is the list of datasets the home page shows. It gets
rebuilt after any agent run:

```sh
# Batch refresh — reads every per-dataset data.json from the bucket
python -m services.page_builder.manifest --bucket govdata-content
# or local dev
python -m services.page_builder.manifest --local frontend/public/data
```

Wire it into the end of each Cloud Function invocation (easiest) or run it
as a scheduled job (Cloud Scheduler → Cloud Function).

## 5. End-to-end smoke

```sh
# Set env vars, then:
python -m services.page_builder.main c5ac01fb-c7ef-4e5e-ba81-e9e11c6f7bd9 \
    --out /tmp/gd-test
ls /tmp/gd-test/datasets/c5ac01fb-c7ef-4e5e-ba81-e9e11c6f7bd9/
# Expected: index.html, data.json
```

If the agent output is sound, deploy: push the Cloud Function, seed a
couple of datasets from the scanner, and check the CDN.
