"""Model-agnostic page-builder test harness (manual-run only).

Drives a Kimi / Claude / OpenAI model through the Managed-Agents tool surface
(`bash`, `code_execution`, `web_fetch`, `web_search`) using **PydanticAI** for
the agent loop and **Podman + llm-sandbox** for the bash/python sandbox.

**Local-only install.** The dependencies for this module live in a separate
file that the production Cloud Run / Cloud Build images deliberately do
NOT install:

    pip install -r services/page_builder/requirements.txt \\
                -r services/page_builder/requirements-test.txt

Single implementation per concern (per `feedback_one_path_default` memory):

- Agent loop  : PydanticAI `Agent`
- Sandbox     : `services.page_builder.podman_sandbox.PodmanSandbox`
- web_fetch   : `httpx`
- web_search  : `duckduckgo-search` (DDG)
- Output FS   : `/tmp/session/outputs/` inside the container

The `model` parameter accepts:
- `kimi-k2.6` (default) — routes to Moonshot's OpenAI-compat endpoint;
  needs `MOONSHOT_API_KEY`.
- `grok-4.3` (and any other `grok-*`) — routes to xAI's OpenAI-compat
  endpoint at https://api.x.ai/v1; needs `XAI_API_KEY`.
- `anthropic:claude-sonnet-4-6` / `anthropic:claude-haiku-4-5` — routes
  through PydanticAI's native Anthropic provider; needs `ANTHROPIC_API_KEY`.
- `openai:gpt-...` — needs `OPENAI_API_KEY`.

Test-only path. Writes outputs to a local directory for visual comparison
against the live govil.ai pages. Does NOT touch Firestore or GCS, and is
never imported by `pipeline.py`, `publish.py`, or `session_runner.run_session`.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import httpx
from pydantic_ai import Agent, RunContext

from .schema import AgentData
from .session_runner import _sanitize_content_html, build_user_message

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
SYSTEM_PROMPT_PATH = REPO_ROOT / "agent" / "govdata-agent-kimi.system.md"

CONTENT_FILENAME = "content.html"
AGENT_DATA_FILENAME = "agent_data.json"
OUTPUTS_DIR_IN_SANDBOX = "/tmp/session/outputs"

# Browser UA the data.gov.il WAF requires (data_gov_il_api_quirks memory).
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

STDOUT_CAP_BYTES = 100_000
WEB_FETCH_CAP_BYTES = 200_000
SEARCH_SNIPPET_CAP = 2_000

# Per-model token prices in $/1M tokens. Sources:
#   Anthropic: https://platform.claude.com/docs/en/about-claude/pricing
#   Moonshot:  https://platform.kimi.ai/docs/pricing
#   xAI:       https://console.x.ai (per-team; not in public docs)
# Add a row here to make a model's cost trackable; otherwise the runner
# logs `cost: unknown` and the cost.json `tokens_usd` / `total_usd`
# fields stay null (the batch summary handles unpriced runs gracefully).
PRICE_TABLE: dict[str, dict[str, float]] = {
    "kimi-k2.6":                  {"input": 0.60, "cached": 0.15, "output": 2.50},
    "kimi-k2.5":                  {"input": 0.44, "cached": 0.11, "output": 2.00},
    "grok-4.3":                   {"input": 1.25, "cached": 0.20, "output": 2.50},
    "anthropic:claude-sonnet-4-6": {"input": 3.00, "cached": 0.30, "output": 15.00},
    "anthropic:claude-haiku-4-5":  {"input": 1.00, "cached": 0.10, "output": 5.00},
    "anthropic:claude-opus-4-7":   {"input": 5.00, "cached": 0.50, "output": 25.00},
}


def _truncate(s: str | list[str], cap: int) -> str:
    if isinstance(s, list):
        s = "".join(s)
    if len(s) <= cap:
        return s
    return s[:cap] + f"\n... [truncated {len(s) - cap} bytes]"


def _exec_to_dict(exe) -> dict:
    """Convert a `_Execution` (PodmanSandbox) into the JSON-able dict the
    PydanticAI tool layer returns to the model."""
    return {
        "stdout": _truncate(exe.logs.stdout or "", STDOUT_CAP_BYTES),
        "stderr": _truncate(exe.logs.stderr or "", STDOUT_CAP_BYTES),
        "error": (
            {"name": exe.error.name, "value": exe.error.value}
            if exe.error else None
        ),
    }


@dataclass
class Deps:
    """Live resources injected into every tool call via RunContext."""
    sandbox: Any                   # PodmanSandbox
    httpx_client: httpx.Client
    bash_calls: int = 0
    code_calls: int = 0
    fetch_calls: int = 0
    search_calls: int = 0
    # Used only for verbose log labelling; harmless if left default.
    dataset_id: str = ""


def _summarize_arg(s: str, cap: int = 80) -> str:
    """One-line preview of a tool argument for log lines."""
    s = (s or "").strip().replace("\n", " ⏎ ")
    return s if len(s) <= cap else s[:cap - 1] + "…"


def _summarize_run_result(d: dict) -> str:
    """One-line outcome summary for bash/code_execution result dicts."""
    out = (d.get("stdout") or "")
    err = (d.get("stderr") or "")
    err_tag = f" stderr={len(err)}B" if err else ""
    err_flag = f" error={d['error']!r}" if d.get("error") else ""
    return f"stdout={len(out)}B{err_tag}{err_flag}"


@dataclass
class TestSessionResult:
    dataset_id: str
    model: str
    out_dir: Path
    content_html_path: Path
    agent_data_path: Path
    transcript_path: Path
    cost_path: Path
    iterations: int
    elapsed_seconds: float
    usage: dict[str, int]
    cost_usd: dict[str, float]
    sandbox_files: list[str] = field(default_factory=list)


def _load_system_prompt() -> str:
    if not SYSTEM_PROMPT_PATH.exists():
        raise FileNotFoundError(
            f"{SYSTEM_PROMPT_PATH} missing — run "
            "`python -m services.page_builder._build_kimi_system` first"
        )
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


_OPENAI_COMPAT_PROVIDERS: dict[str, dict[str, str]] = {
    # Each entry maps a model-id prefix to the OpenAI-compat endpoint that
    # serves it. The model id is forwarded verbatim — the provider treats
    # the OpenAI SDK as a transport.
    "kimi-": {
        "base_url": "https://api.moonshot.ai/v1",
        "env_var": "MOONSHOT_API_KEY",
        "label":   "Moonshot",
    },
    "grok-": {
        "base_url": "https://api.x.ai/v1",
        "env_var": "XAI_API_KEY",
        "label":   "xAI",
    },
}


def _build_pydantic_model(model_id: str):
    """Resolve a model id to a PydanticAI model handle.

    `kimi-*` and `grok-*` route to their respective OpenAI-compat endpoints
    (Moonshot / xAI) via PydanticAI's `OpenAIChatModel`. Everything else
    is passed through as-is so PydanticAI's provider-prefix shorthand
    (`anthropic:...`, `openai:...`, etc.) can resolve it. Each provider
    reads its own standard env var.
    """
    for prefix, cfg in _OPENAI_COMPAT_PROVIDERS.items():
        if not model_id.startswith(prefix):
            continue
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider
        api_key = os.environ.get(cfg["env_var"])
        if not api_key:
            raise RuntimeError(
                f"model={model_id!r} ({cfg['label']}) but "
                f"{cfg['env_var']} not set"
            )
        return OpenAIChatModel(
            model_id,
            provider=OpenAIProvider(
                base_url=cfg["base_url"],
                api_key=api_key,
            ),
        )
    return model_id


def _build_agent(*, model, system_prompt: str) -> Agent[Deps, str]:
    agent = Agent(model=model, deps_type=Deps, system_prompt=system_prompt, retries=2)

    @agent.tool
    def bash(ctx: RunContext[Deps], cmd: str) -> dict:
        """Run a shell command inside the sandbox (state persists between calls).

        Args:
            cmd: shell command. cwd, exported env, and written files persist.
        """
        ctx.deps.bash_calls += 1
        n = ctx.deps.bash_calls
        ds = ctx.deps.dataset_id[:8]
        log.info("test[%s]: bash#%d $ %s", ds, n, _summarize_arg(cmd))
        t0 = time.monotonic()
        out = _exec_to_dict(ctx.deps.sandbox.run_code(cmd, language="bash", timeout=120))
        log.info(
            "test[%s]: bash#%d done in %.1fs — %s",
            ds, n, time.monotonic() - t0, _summarize_run_result(out),
        )
        return out

    @agent.tool
    def code_execution(ctx: RunContext[Deps], code: str) -> dict:
        """Execute Python in the sandbox.

        Args:
            code: Python source.
        """
        ctx.deps.code_calls += 1
        n = ctx.deps.code_calls
        ds = ctx.deps.dataset_id[:8]
        log.info("test[%s]: python#%d >>> %s", ds, n, _summarize_arg(code))
        t0 = time.monotonic()
        out = _exec_to_dict(ctx.deps.sandbox.run_code(code, language="python", timeout=120))
        log.info(
            "test[%s]: python#%d done in %.1fs — %s",
            ds, n, time.monotonic() - t0, _summarize_run_result(out),
        )
        return out

    @agent.tool
    def web_fetch(ctx: RunContext[Deps], url: str) -> dict:
        """Fetch a URL over HTTPS, returning the text body (HTML/JSON/etc).

        Args:
            url: fully-qualified http(s) URL.
        """
        ctx.deps.fetch_calls += 1
        n = ctx.deps.fetch_calls
        ds = ctx.deps.dataset_id[:8]
        log.info("test[%s]: fetch#%d %s", ds, n, _summarize_arg(url, cap=120))
        t0 = time.monotonic()
        try:
            r = ctx.deps.httpx_client.get(
                url,
                headers={"User-Agent": BROWSER_UA, "Accept": "*/*"},
                timeout=30.0,
                follow_redirects=True,
            )
        except httpx.HTTPError as e:
            log.info(
                "test[%s]: fetch#%d failed in %.1fs — %s",
                ds, n, time.monotonic() - t0, type(e).__name__,
            )
            return {"status": 0, "error": f"{type(e).__name__}: {e}", "text": ""}
        body = _truncate(r.text, WEB_FETCH_CAP_BYTES)
        log.info(
            "test[%s]: fetch#%d done in %.1fs — status=%d body=%dB",
            ds, n, time.monotonic() - t0, r.status_code, len(body),
        )
        return {
            "status": r.status_code,
            "content_type": r.headers.get("content-type", ""),
            "url": str(r.url),
            "text": body,
        }

    @agent.tool
    def web_search(ctx: RunContext[Deps], query: str, max_results: int = 5) -> dict:
        """Search the public web (DuckDuckGo), returning titles + URLs + snippets.

        Args:
            query: search query (any language).
            max_results: 1-10.
        """
        ctx.deps.search_calls += 1
        n = ctx.deps.search_calls
        ds = ctx.deps.dataset_id[:8]
        max_results = max(1, min(int(max_results or 5), 10))
        log.info("test[%s]: search#%d %r (max=%d)", ds, n, _summarize_arg(query), max_results)
        t0 = time.monotonic()
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddg:
                hits = list(ddg.text(query, max_results=max_results))
        except Exception as e:
            log.info(
                "test[%s]: search#%d failed in %.1fs — %s",
                ds, n, time.monotonic() - t0, type(e).__name__,
            )
            return {"error": f"{type(e).__name__}: {e}", "results": []}
        results = [
            {
                "title": h.get("title", ""),
                "url": h.get("href") or h.get("url") or "",
                "snippet": _truncate(h.get("body") or h.get("snippet") or "", SEARCH_SNIPPET_CAP),
            }
            for h in hits[:max_results]
        ]
        log.info(
            "test[%s]: search#%d done in %.1fs — %d results",
            ds, n, time.monotonic() - t0, len(results),
        )
        return {"results": results}

    return agent


def _serialize_messages(messages: list) -> list[dict]:
    out = []
    for m in messages:
        try:
            out.append(m.model_dump(mode="json"))
        except Exception:
            out.append({"_repr": repr(m)})
    return out


def _safe_dump(obj) -> dict:
    if obj is None:
        return {}
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump()
        except Exception:
            pass
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in vars(obj).items() if not k.startswith("_")}
    return {}


def _extract_usage(result_usage) -> dict[str, int]:
    u = result_usage if isinstance(result_usage, dict) else _safe_dump(result_usage)
    input_tokens = int(u.get("input_tokens") or u.get("request_tokens") or 0)
    output_tokens = int(u.get("output_tokens") or u.get("response_tokens") or 0)
    total = int(u.get("total_tokens") or (input_tokens + output_tokens))
    details = u.get("details") or {}
    cache_read = int(
        details.get("cache_read_input_tokens")
        or details.get("cached_tokens")
        or details.get("prompt_cache_hit_tokens")
        or 0
    )
    cache_write = int(
        details.get("cache_creation_input_tokens")
        or details.get("cache_write_tokens")
        or 0
    )
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total,
        "cache_read_tokens": cache_read,
        "cache_write_tokens": cache_write,
    }


def _compute_cost(*, model: str, usage: dict[str, int]) -> dict[str, Any]:
    prices = PRICE_TABLE.get(model)
    if prices is None:
        return {"tokens_usd": None, "total_usd": None, "note": "model not in PRICE_TABLE"}
    cached = usage["cache_read_tokens"]
    uncached_input = max(usage["input_tokens"] - cached, 0)
    tokens_usd = (
        uncached_input * prices["input"]
        + cached * prices["cached"]
        + usage["output_tokens"] * prices["output"]
    ) / 1_000_000
    return {
        "tokens_usd": round(tokens_usd, 6),
        "total_usd": round(tokens_usd, 6),  # only cost component
    }


def run_test_session(
    *,
    dataset_id: str,
    title: str,
    notes: str,
    org_title: str,
    primary_resource_id: Optional[str],
    out_dir: Path,
    model: str = "kimi-k2.6",
    max_iters: int = 30,  # noqa: ARG001 - PydanticAI controls retries; kept for caller parity
) -> TestSessionResult:
    """Run a model+sandbox session for one CKAN dataset; write outputs to `out_dir`."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    system_prompt = _load_system_prompt()
    user_msg = build_user_message(
        dataset_id=dataset_id,
        title=title,
        notes=notes,
        org_title=org_title,
        primary_resource_id=primary_resource_id,
        outputs_dir=OUTPUTS_DIR_IN_SANDBOX,
    )

    from .podman_sandbox import PodmanSandbox

    log.info("test[%s]: starting Podman sandbox + model=%s", dataset_id[:8], model)
    sandbox = PodmanSandbox.create()
    httpx_client = httpx.Client()
    deps = Deps(sandbox=sandbox, httpx_client=httpx_client, dataset_id=dataset_id)

    started = time.monotonic()
    try:
        py_model = _build_pydantic_model(model)
        agent = _build_agent(model=py_model, system_prompt=system_prompt)
        log.info("test[%s]: agent.run_sync", dataset_id[:8])
        result = agent.run_sync(user_msg, deps=deps)
        elapsed = time.monotonic() - started

        try:
            content_html_bytes = sandbox.files.read(
                f"{OUTPUTS_DIR_IN_SANDBOX}/{CONTENT_FILENAME}"
            )
            agent_data_bytes = sandbox.files.read(
                f"{OUTPUTS_DIR_IN_SANDBOX}/{AGENT_DATA_FILENAME}"
            )
        except Exception as e:
            raise RuntimeError(
                f"agent did not produce both output files: {e}. "
                f"Inspect transcript at {out_dir / 'transcript.json'}"
            ) from e

        content_html = content_html_bytes.decode("utf-8") if isinstance(content_html_bytes, (bytes, bytearray)) else str(content_html_bytes)
        agent_data_raw = bytes(agent_data_bytes) if isinstance(agent_data_bytes, (bytes, bytearray)) else str(agent_data_bytes).encode("utf-8")

        content_html = _sanitize_content_html(content_html, dataset_id=dataset_id)
        agent_data = AgentData.model_validate_json(agent_data_raw)

        sandbox_files: list[str] = []
        try:
            for entry in sandbox.files.list(OUTPUTS_DIR_IN_SANDBOX):
                sandbox_files.append(getattr(entry, "name", str(entry)))
        except Exception:
            pass

    finally:
        try:
            httpx_client.close()
        except Exception:
            pass
        try:
            sandbox.kill()
        except Exception as e:
            log.warning("test[%s]: sandbox.kill failed: %s", dataset_id[:8], e)

    content_html_path = out_dir / CONTENT_FILENAME
    agent_data_path = out_dir / AGENT_DATA_FILENAME
    transcript_path = out_dir / "transcript.json"
    cost_path = out_dir / "cost.json"

    content_html_path.write_text(content_html, encoding="utf-8")
    agent_data_path.write_text(
        json.dumps(agent_data.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    messages = result.all_messages()
    transcript_path.write_text(
        json.dumps(_serialize_messages(messages), ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    usage = _extract_usage(result.usage())
    cost = _compute_cost(model=model, usage=usage)
    cost_path.write_text(
        json.dumps(
            {
                "model": model,
                "elapsed_seconds": round(elapsed, 2),
                "usage": usage,
                "cost_usd": cost,
                "tool_calls": {
                    "bash": deps.bash_calls,
                    "code_execution": deps.code_calls,
                    "web_fetch": deps.fetch_calls,
                    "web_search": deps.search_calls,
                },
                "sandbox_files": sandbox_files,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    iterations = sum(
        1 for m in messages
        if hasattr(m, "parts") and any(
            type(p).__name__ in ("ToolCallPart", "ToolReturnPart") for p in m.parts
        )
    )

    return TestSessionResult(
        dataset_id=dataset_id,
        model=model,
        out_dir=out_dir,
        content_html_path=content_html_path,
        agent_data_path=agent_data_path,
        transcript_path=transcript_path,
        cost_path=cost_path,
        iterations=iterations,
        elapsed_seconds=elapsed,
        usage=usage,
        cost_usd=cost,
        sandbox_files=sandbox_files,
    )


# Back-compat aliases for callers that already imported the old names.
KimiSessionResult = TestSessionResult
run_kimi_session = run_test_session
