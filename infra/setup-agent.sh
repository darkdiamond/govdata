#!/usr/bin/env bash
# One-time setup for the GovData page-author Managed Agent.
#
# Requires:
#   - ANTHROPIC_API_KEY in env
#   - `ant` CLI on PATH — see https://platform.claude.com/docs/en/api/sdks/cli.md
#   - ANTHROPIC_WORKSPACE_ID (optional; ant picks the default workspace)
#
# Outputs AGENT_ID and ENV_ID to stdout. Store them in:
#   GCP:   Secret Manager or function env vars
#   Local: .env file (see .env.example)
set -euo pipefail

command -v ant >/dev/null || {
  echo "ant CLI not found. Install: https://github.com/anthropics/anthropic-cli/releases" >&2
  exit 2
}
: "${ANTHROPIC_API_KEY:?ANTHROPIC_API_KEY must be set}"

cd "$(dirname "$0")/.."

echo "==> creating environment from agent/govdata-env.yaml"
ENV_ID=$(ant beta:environments create < agent/govdata-env.yaml --transform id --format yaml)
echo "ENV_ID=$ENV_ID"

echo "==> creating agent from agent/govdata-agent.yaml"
AGENT_ID=$(ant beta:agents create < agent/govdata-agent.yaml --transform id --format yaml)
echo "AGENT_ID=$AGENT_ID"

echo
echo "# Add these to your .env (or deployment env vars):"
echo "ANTHROPIC_AGENT_ID=$AGENT_ID"
echo "ANTHROPIC_ENV_ID=$ENV_ID"
echo
echo "# To update the agent's system prompt later (creates a new version):"
echo "#   ANTHROPIC_AGENT_ID=$AGENT_ID python3 infra/update-agent.py"
