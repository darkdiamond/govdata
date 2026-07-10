# Local test-harness sandbox image: the upstream llm-sandbox Python image
# plus the analysis libs agents actually reach for, so sessions don't
# `pip install` mid-run (time + network + a failure mode). Build once:
#
#   podman build -t govdata-sandbox:latest \
#     -f services/page_builder/sandbox.Containerfile .
#
# then point the harness at it (e.g. in .env):
#
#   PODMAN_SANDBOX_IMAGE=localhost/govdata-sandbox:latest
#
# Production (LocalSandbox in the builder container) gets pandas via
# services/page_builder/requirements.txt instead.
FROM ghcr.io/vndee/sandbox-python-311-bullseye

RUN pip install --no-cache-dir "pandas>=2,<3"
