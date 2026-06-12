"""Subprocess sandbox for production agent sessions.

Same surface as `podman_sandbox.PodmanSandbox` (`run_code`, `files.read`,
`files.list`, `kill`) but executes directly in the builder container via
`subprocess` — Cloud Run can't nest containers, so the (single-tenant,
ephemeral) container itself is the isolation boundary. Each session gets
a private working directory; the agent's prompt uses relative scratch
paths and the per-session OUTPUTS_DIR, so concurrent sessions in one
container never share files.

Hardening within that boundary:
- scrubbed env: PATH/HOME/LANG only — no GCP credentials vars, no
  OPENROUTER key (HOME points into the session workdir).
- per-command wall-clock timeout (default 120s, SIGKILL on expiry).
- output size is capped by the caller (model_harness truncation).

Accepted residual risk (documented in CLAUDE.md): a process in the
container can reach the GCP metadata server and obtain the builder
service account's token. The SA is scoped to Firestore + the staging
bucket + running the publish trigger only.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from pathlib import Path

from .podman_sandbox import _Error, _Execution, _FileEntry, _Logs

log = logging.getLogger(__name__)

_BASE_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"


class _Files:
    def __init__(self, sb: "LocalSandbox"):
        self._sb = sb

    def read(self, path: str) -> bytes:
        p = Path(path)
        if not p.is_absolute():
            p = self._sb.workdir / p
        if not p.is_file():
            raise FileNotFoundError(f"sandbox file not readable: {p}")
        return p.read_bytes()

    def list(self, path: str) -> list[_FileEntry]:
        p = Path(path)
        if not p.is_absolute():
            p = self._sb.workdir / p
        if not p.is_dir():
            return []
        return [
            _FileEntry(name=c.name, path=str(c))
            for c in sorted(p.iterdir())
        ]


class LocalSandbox:
    """Per-session subprocess executor with a private workdir."""

    def __init__(self, workdir: Path):
        self.workdir = workdir
        self.files = _Files(self)
        self._closed = False
        self._env = {
            "PATH": _BASE_PATH,
            "HOME": str(workdir),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PYTHONUNBUFFERED": "1",
        }

    @classmethod
    def create(cls, workdir: str | Path) -> "LocalSandbox":
        wd = Path(workdir)
        (wd / "outputs").mkdir(parents=True, exist_ok=True)
        log.info("LocalSandbox: workdir=%s", wd)
        return cls(wd)

    def kill(self) -> None:
        if self._closed:
            return
        self._closed = True
        shutil.rmtree(self.workdir, ignore_errors=True)

    def run_code(
        self,
        code: str,
        *,
        language: str = "python",
        timeout: int = 120,
    ) -> _Execution:
        if language == "bash":
            argv = ["bash", "-c", code]
        elif language in ("python", "py"):
            argv = [sys.executable, "-c", code]
        else:
            return _Execution(error=_Error(name="UnsupportedLanguage", value=language))
        try:
            proc = subprocess.run(
                argv,
                cwd=self.workdir,
                env=self._env,
                capture_output=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as e:
            return _Execution(
                logs=_Logs(
                    stdout=(e.stdout or b"").decode("utf-8", errors="replace"),
                    stderr=(e.stderr or b"").decode("utf-8", errors="replace"),
                ),
                error=_Error(name="Timeout", value=f"killed after {timeout}s"),
            )
        out = proc.stdout.decode("utf-8", errors="replace")
        err = proc.stderr.decode("utf-8", errors="replace")
        error = (
            _Error(name="NonZeroExit", value=f"exit code {proc.returncode}")
            if proc.returncode != 0
            else None
        )
        return _Execution(logs=_Logs(stdout=out, stderr=err), error=error)
