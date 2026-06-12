"""Extract the Managed Agents YAML `system:` block into a single Markdown file
the model-test harness sends as `system`.

Third-party models have no concept of Anthropic "skills". The agent YAML's
`system:` block is the full instruction set our agent runs with on Anthropic —
the design-skill content was merged directly into the yaml in commit 67a01ee,
so the yaml is the single source of truth. Run this whenever the yaml changes:

    python -m services.page_builder._build_harness_system

Writes `agent/govdata-agent-harness.system.md` (committed). The runner reads
that file at startup so what's sent to the model is grep-able in the repo.
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT_YAML = REPO_ROOT / "agent" / "govdata-agent.yaml"
OUT = REPO_ROOT / "agent" / "govdata-agent-harness.system.md"

# Anthropic Managed Agents pin output to /mnt/session/outputs/ — that path
# isn't user-writable on a normal Linux/WSL host, so the harness sandbox (E2B
# or local subprocess sandbox) writes under /tmp/ instead. Substitute the
# path globally in the prompt so the agent's self-checks reference the
# real location.
PATH_SUBSTITUTIONS = [
    ("/mnt/session/outputs", "/tmp/session/outputs"),
    # The self-check script is mounted at /mnt/session/uploads/check.py by
    # Managed Agents; the local harness copies agent/skills/check.py to the
    # mirrored /tmp path at sandbox startup (model_harness.run_test_session).
    ("/mnt/session/uploads", "/tmp/session/uploads"),
]


def build() -> str:
    cfg = yaml.safe_load(AGENT_YAML.read_text(encoding="utf-8"))
    system = cfg.get("system", "")
    if not system:
        raise SystemExit(f"no `system:` key found in {AGENT_YAML}")
    text = system.rstrip() + "\n"
    for old, new in PATH_SUBSTITUTIONS:
        text = text.replace(old, new)
    return text


def main() -> None:
    OUT.write_text(build(), encoding="utf-8")
    size = OUT.stat().st_size
    print(f"wrote {OUT} ({size:,} bytes)")


if __name__ == "__main__":
    main()
