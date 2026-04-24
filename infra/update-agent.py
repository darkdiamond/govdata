#!/usr/bin/env python3
"""Update the GovData Managed Agent in-place from agent/govdata-agent.yaml.

Counterpart to `infra/setup-agent.sh`, which CREATES the agent. This script
MUTATES the existing agent identified by ANTHROPIC_AGENT_ID — it fetches
the current version, then submits an update carrying every top-level field
in the yaml (name, description, model, system, tools). The API increments
the version on success; the new version is printed at the end.

Requires:
  ANTHROPIC_API_KEY     — the same key used by setup-agent.sh
  ANTHROPIC_AGENT_ID    — the agent_id printed by setup-agent.sh

Usage:
  python3 infra/update-agent.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml
from anthropic import Anthropic

MA_BETA = "managed-agents-2026-04-01"

# Fields in agent/govdata-agent.yaml we forward to the update API.
# `skills` and `mcp_servers` would also be valid but aren't used in this
# project's yaml. Metadata is not versioned, so we leave it alone.
UPDATABLE_FIELDS = ("name", "description", "model", "system", "tools")


def main() -> int:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    agent_id = os.environ.get("ANTHROPIC_AGENT_ID")
    if not api_key:
        print("ANTHROPIC_API_KEY must be set", file=sys.stderr)
        return 2
    if not agent_id:
        print(
            "ANTHROPIC_AGENT_ID must be set — run infra/setup-agent.sh once and "
            "export the agent_id it prints",
            file=sys.stderr,
        )
        return 2

    repo_root = Path(__file__).resolve().parents[1]
    yaml_path = repo_root / "agent" / "govdata-agent.yaml"
    with yaml_path.open("r", encoding="utf-8") as f:
        spec = yaml.safe_load(f)

    client = Anthropic(api_key=api_key)

    current = client.beta.agents.retrieve(agent_id, betas=[MA_BETA])
    print(f"agent_id:        {current.id}")
    print(f"current version: {current.version}")
    print(f"current name:    {current.name}")

    kwargs: dict = {"version": current.version, "betas": [MA_BETA]}
    for key in UPDATABLE_FIELDS:
        if key in spec and spec[key] is not None:
            kwargs[key] = spec[key]

    updated = client.beta.agents.update(agent_id, **kwargs)
    print(f"new version:     {updated.version}")
    print("ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
