"""Podman + llm-sandbox adapter, shaped like e2b_code_interpreter.Sandbox.

Real isolation, free, runs locally. The agent's `bash` and `code_execution`
tools both route into a single rootless Podman container with persistent FS
between calls. `files.read` pulls files out via llm-sandbox's
`copy_from_runtime`.

Hardened defaults:

- `cap_drop=["ALL"]` — agent can't escalate.
- `security_opt=["no-new-privileges"]` — defence in depth.
- `mem_limit=1g`, `cpu_count=1` — bounded resources.
- `network_mode="bridge"` — agent needs to curl data.gov.il from inside the
  sandbox. (The host's network is reachable, but `cap_drop=ALL` blocks raw
  sockets, port binding, etc.)

Required by `model_harness.py`:

    sb = PodmanSandbox.create()
    sb.run_code(code, language="bash"|"python", timeout=120) -> _Execution
    sb.files.read(container_path) -> bytes
    sb.files.list(container_path) -> list[_FileEntry]
    sb.kill()

`_Execution` mimics the e2b shape (`.logs.stdout`, `.logs.stderr`, `.error`,
`.results`) so the runner's `_exec_to_dict` works unchanged.
"""
from __future__ import annotations

import logging
import os
import shlex
from dataclasses import dataclass, field
from typing import Optional


def _sh_quote(s: str) -> str:
    return shlex.quote(s)

log = logging.getLogger(__name__)

# Pre-built image with Python 3.11 + curl + common tooling. Pinning a tag
# keeps runs reproducible across the test campaign. Override with
# PODMAN_SANDBOX_IMAGE — normally localhost/govdata-sandbox:latest, the
# derived image with pandas preinstalled (see sandbox.Containerfile).
DEFAULT_IMAGE = (
    os.environ.get("PODMAN_SANDBOX_IMAGE")
    or "ghcr.io/vndee/sandbox-python-311-bullseye"
)

DEFAULT_RUNTIME_CONFIGS = {
    "mem_limit": "1g",
    "cpu_count": 1,
    "cap_drop": ["ALL"],
    "security_opt": ["no-new-privileges"],
    "network_mode": "bridge",
}


@dataclass
class _Logs:
    stdout: str = ""
    stderr: str = ""


@dataclass
class _Error:
    name: str
    value: str


@dataclass
class _Result:
    text: str


@dataclass
class _Execution:
    logs: _Logs = field(default_factory=_Logs)
    error: Optional[_Error] = None
    results: list[_Result] = field(default_factory=list)


class _FileEntry:
    def __init__(self, name: str, path: str):
        self.name = name
        self.path = path


class _Files:
    def __init__(self, sb: "PodmanSandbox"):
        self._sb = sb

    def read(self, container_path: str) -> bytes:
        # We can't use llm-sandbox's copy_from_runtime here: rootless Podman
        # v4.9 returns single-file tar archives with the file entry marked
        # as a directory (isdir=True, size=0), so tar.extract() makes a
        # zero-byte dir on the host instead of writing the file. Round-trip
        # through `base64 -w0 < path` instead — preserves arbitrary bytes
        # and avoids the broken archive path entirely.
        import base64
        out = self._sb._session.execute_command(
            f"bash -c {_sh_quote(f'base64 -w0 {_sh_quote(container_path)}')}"
        )
        if getattr(out, "exit_code", 0) != 0:
            raise FileNotFoundError(
                f"sandbox file not readable: {container_path}: {out.stderr or '(no stderr)'}"
            )
        return base64.b64decode((out.stdout or "").strip())

    def list(self, container_path: str) -> list[_FileEntry]:
        # Same shell-wrap as run_code(language='bash') — execute_command is
        # argv-style, so wildcards / `2>/dev/null` would be passed literally.
        out = self._sb._session.execute_command(
            f"bash -c {_sh_quote(f'ls -1 {container_path} 2>/dev/null')}"
        )
        if getattr(out, "exit_code", 0) != 0:
            return []
        names = (out.stdout or "").splitlines()
        return [_FileEntry(name=n, path=f"{container_path.rstrip('/')}/{n}")
                for n in names if n]


class PodmanSandbox:
    """Podman-backed sandbox; same surface as e2b_code_interpreter.Sandbox."""

    def __init__(self, session, *, image: str = DEFAULT_IMAGE):
        self._session = session
        self.image = image
        self.files = _Files(self)
        self._closed = False

    @classmethod
    def create(
        cls,
        *,
        image: str = DEFAULT_IMAGE,
        runtime_configs: Optional[dict] = None,
    ) -> "PodmanSandbox":
        from llm_sandbox import SandboxSession

        rc = dict(DEFAULT_RUNTIME_CONFIGS)
        if runtime_configs:
            rc.update(runtime_configs)
        log.info("PodmanSandbox: starting image=%s", image)
        # Manually drive __enter__/__exit__ so the session outlives this
        # method call. `kill()` calls __exit__.
        session = SandboxSession(
            backend="podman",
            lang="python",
            image=image,
            runtime_configs=rc,
            keep_template=True,            # don't rebuild the image between sessions
            encoding_errors="replace",     # agent emits Hebrew; output cap can split a multibyte
        )
        session.__enter__()
        sb = cls(session, image=image)
        # Make the path the harness system prompt expects (rewritten to /tmp/).
        sb.run_code("mkdir -p /tmp/session/outputs", language="bash", timeout=10)
        return sb

    def kill(self) -> None:
        if self._closed:
            return
        self._closed = True
        # llm-sandbox's __exit__ stops the container but, with
        # keep_template=True, leaves it on disk — so repeated test runs leak
        # exited containers. Explicitly remove ours after stopping.
        container = getattr(self._session, "container", None)
        try:
            self._session.__exit__(None, None, None)
        except Exception as e:
            log.warning("PodmanSandbox.kill: __exit__ failed: %s", e)
        if container is not None:
            try:
                container.remove(force=True)
            except Exception:
                # Expected on the happy path — llm-sandbox's __exit__
                # already removed it. Only useful when __exit__ raised.
                pass

    # ---- core API ----

    def run_code(
        self,
        code: str,
        *,
        language: str = "python",
        timeout: int = 120,  # noqa: ARG002 - llm-sandbox doesn't expose per-call timeout cleanly
    ) -> _Execution:
        if language == "bash":
            # llm-sandbox's execute_command is argv-style (no shell), so
            # `>`, `|`, `&&` etc. wouldn't be interpreted. Wrap explicitly.
            wrapped = f"bash -c {_sh_quote(code)}"
            out = self._session.execute_command(wrapped)
            stdout = getattr(out, "stdout", "") or ""
            stderr = getattr(out, "stderr", "") or ""
            exit_code = getattr(out, "exit_code", 0) or 0
            err = _Error(name="NonZeroExit", value=f"exit code {exit_code}") if exit_code != 0 else None
            return _Execution(logs=_Logs(stdout=stdout, stderr=stderr), error=err)

        if language in ("python", "py"):
            out = self._session.run(code)
            stdout = getattr(out, "stdout", "") or ""
            stderr = getattr(out, "stderr", "") or ""
            exit_code = getattr(out, "exit_code", 0) or 0
            err = _Error(name="PythonError", value=f"exit code {exit_code}") if exit_code != 0 else None
            return _Execution(logs=_Logs(stdout=stdout, stderr=stderr), error=err)

        return _Execution(error=_Error(name="UnsupportedLanguage", value=language))
