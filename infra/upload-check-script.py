#!/usr/bin/env python3
"""Upload `agent/skills/check.py` to the Files API and print its file_id.

The Managed Agents env (`agent/govdata-env.yaml`) is type=cloud with no
custom container image, so we can't bake `check.py` into the image.
Instead we upload it once via the Files API and attach it as a session
resource at `/workspace/check.py` on every session create
(`services/page_builder/session_runner.py`). The agent then runs the
check via:

    python3 /workspace/check.py content.html agent_data.json

Re-run this script whenever `agent/skills/check.py` changes — files
are immutable in the Files API, so each edit needs a fresh upload and
the new file_id propagated to ANTHROPIC_CHECK_PY_FILE_ID.

Usage:
    ANTHROPIC_API_KEY=... python3 infra/upload-check-script.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from anthropic import Anthropic

FILES_BETA = "files-api-2025-04-14"


def main() -> int:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY must be set", file=sys.stderr)
        return 2

    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "agent" / "skills" / "check.py"
    if not script_path.is_file():
        print(f"missing: {script_path}", file=sys.stderr)
        return 2

    client = Anthropic(api_key=api_key)
    with script_path.open("rb") as f:
        uploaded = client.beta.files.upload(
            file=("check.py", f, "text/x-python"),
            betas=[FILES_BETA],
        )
    print(f"uploaded:        {script_path}")
    print(f"file_id:         {uploaded.id}")
    print(f"size_bytes:      {uploaded.size_bytes}")
    print()
    print("# Add to your .env (or deployment env vars):")
    print(f"ANTHROPIC_CHECK_PY_FILE_ID={uploaded.id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
