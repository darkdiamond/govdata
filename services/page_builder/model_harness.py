"""The page-builder agent loop — shared by production and local testing.

Drives any model through the agent tool surface (`bash`,
`code_execution`, `web_fetch`, `web_search`) using **PydanticAI**, on a
pluggable sandbox backend:

- production (`agent_runner.py`): `LocalSandbox` — subprocesses with a
  private per-session workdir inside the builder container.
- local testing (`run_test_session` + `cli/model_test.py`):
  `PodmanSandbox` — a rootless Podman container (needs the extra deps
  in requirements-test.txt).

Single implementation per concern (per `feedback_one_path_default` memory):

- Agent loop  : PydanticAI `Agent` (`run_agent_session`)
- web_fetch   : `httpx`
- web_search  : `duckduckgo-search` (DDG)
- System prompt: `agent/system-prompt.md` (canonical, hand-edited);
  per-session paths arrive via the user message (OUTPUTS_DIR /
  CHECK_SCRIPT) so the prompt stays byte-identical across sessions
  for provider prefix caching.

The `model` parameter accepts two forms:
- `<vendor>/<model>` — an OpenRouter model id (`minimax/minimax-m3`,
  `moonshotai/kimi-k2.6`, `x-ai/grok-4.3`, `anthropic/claude-sonnet-4-6`,
  …; browse https://openrouter.ai/models). Routed via PydanticAI's
  `OpenRouterModel`; needs `OPENROUTER_API_KEY`. Usage accounting is on,
  so `cost.json` carries the **actual billed USD** (incl. provider cache
  discounts — the hand-priced estimates were ~6× off for MiniMax direct
  because its compat endpoint hides cache reads). `reasoning_details`
  round-trip on history replay, which interleaved-thinking models
  (MiniMax, Kimi) need for stable tool loops.
- `anthropic:claude-…` — PydanticAI's native Anthropic provider; needs
  `ANTHROPIC_API_KEY`. Kept for calibration runs; cost falls back to the
  static Anthropic price table.

`run_agent_session` returns RAW outputs — validation/persistence belong
to the caller (`agent_runner` in prod; `run_test_session` writes local
artifacts and touches neither Firestore nor GCS).
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
from pydantic_ai import Agent, ModelRetry, RunContext

from .agent_contract import build_user_message, sanitize_content_html
from .schema import AgentData

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
SYSTEM_PROMPT_PATH = REPO_ROOT / "agent" / "system-prompt.md"
CHECK_SCRIPT_PATH = REPO_ROOT / "agent" / "skills" / "check.py"
# Fixed paths used by the Podman test harness (one session per container,
# so they never collide). Production (LocalSandbox) passes per-session
# paths instead.
CHECK_SCRIPT_IN_SANDBOX = "/tmp/session/uploads/check.py"

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

# Fallback prices ($/1M tokens) for the native `anthropic:` calibration
# path only — OpenRouter runs report actual billed cost per response, so
# they never consult a table. Source:
#   https://platform.claude.com/docs/en/about-claude/pricing
PRICE_TABLE: dict[str, dict[str, float]] = {
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


def _provision_check_script(sandbox, target: str = CHECK_SCRIPT_IN_SANDBOX) -> None:
    """Copy agent/skills/check.py into the sandbox at `target` — the
    CHECK_SCRIPT path the session's user message advertises. check.py is
    argv-driven, so any path works. Base64 round-trip because the Podman
    session has no file-write API (see _Files.read for the inverse); the
    same bash works unchanged on LocalSandbox.
    """
    import base64

    if not CHECK_SCRIPT_PATH.exists():
        raise FileNotFoundError(
            f"{CHECK_SCRIPT_PATH} missing — the system prompt's self-check "
            "step depends on it"
        )
    b64 = base64.b64encode(CHECK_SCRIPT_PATH.read_bytes()).decode("ascii")
    target_dir = target.rsplit("/", 1)[0]
    exe = sandbox.run_code(
        f"mkdir -p {target_dir} && "
        f"echo {b64} | base64 -d > {target} && "
        f"python3 -c \"import ast; ast.parse(open('{target}').read())\"",
        language="bash",
        timeout=30,
    )
    if exe.error:
        raise RuntimeError(
            f"failed to provision check.py in sandbox: {exe.error.value}: "
            f"{exe.logs.stderr}"
        )


def _load_system_prompt() -> str:
    if not SYSTEM_PROMPT_PATH.exists():
        raise FileNotFoundError(
            f"{SYSTEM_PROMPT_PATH} missing — the canonical agent system "
            "prompt must ship with the code (and the container image)"
        )
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


def _build_pydantic_model(model_id: str) -> tuple[Any, dict[str, Any]]:
    """Resolve a model id to (PydanticAI model handle, model_settings).

    Two accepted forms:
    - `<vendor>/<model>` — OpenRouter id, routed via `OpenRouterModel`
      with usage accounting enabled (actual billed cost lands in each
      response's `provider_details['cost']`). Needs OPENROUTER_API_KEY.
    - `anthropic:<model>` — PydanticAI's native Anthropic provider,
      kept for harness-vs-Managed-Agents calibration runs.

    The settings dict always carries the load-bearing `max_tokens`
    ceiling (see _build_agent) plus any provider-specific keys.
    """
    base_settings: dict[str, Any] = {"max_tokens": 16384}

    if "/" in model_id:
        from pydantic_ai.models.openrouter import OpenRouterModel
        from pydantic_ai.providers.openrouter import OpenRouterProvider

        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError(
                f"model={model_id!r} is an OpenRouter id but "
                "OPENROUTER_API_KEY is not set"
            )
        # `usage.include` asks OpenRouter for usage accounting: the final
        # response carries billed cost + cached-token counts, which the
        # OpenRouterModel maps into provider_details / RequestUsage.
        base_settings["openrouter_usage"] = {"include": True}
        return (
            OpenRouterModel(model_id, provider=OpenRouterProvider(api_key=api_key)),
            base_settings,
        )

    if model_id.startswith("anthropic:"):
        return model_id, base_settings

    raise RuntimeError(
        f"model={model_id!r} not recognized. Use an OpenRouter id "
        "(<vendor>/<model>, e.g. minimax/minimax-m3 — browse "
        "https://openrouter.ai/models) or anthropic:<model> for the "
        "native calibration path."
    )


def _build_agent(
    *, model, system_prompt: str, model_settings: dict[str, Any]
) -> Agent[Deps, str]:
    # retries=5 + an explicit max_tokens ceiling (in model_settings, set by
    # _build_pydantic_model). The token bump is a real bug-fix, not a
    # defensive knob: Anthropic's streaming adapter (and the corresponding
    # PydanticAI parser path) drops tool_use input arguments when the
    # response hits max_tokens mid-stream, leaving the tool call with
    # `input={}`. Pre-1.91 PydanticAI silently surfaced the truncated
    # call to the agent loop, which then looked like the model emitting
    # empty bash calls. Sonnet's bash heredocs (multi-KB python scripts in
    # `cat <<PY ... PY`) routinely push past 4096 — the previous default.
    # See pydantic-ai #3118 + PR #3137.
    agent = Agent(
        model=model,
        deps_type=Deps,
        system_prompt=system_prompt,
        retries=5,
        model_settings=model_settings,
    )

    @agent.tool
    def bash(
        ctx: RunContext[Deps],
        command: str | None = None,
        restart: bool = False,
    ) -> dict:
        """Run a shell command inside the sandbox (state persists between calls).

        Args:
            command: shell command. cwd, exported env, and written files persist.
            restart: ignored — the sandbox already provides a fresh persistent
                shell per session. Accepted only for compatibility with models
                trained on the Anthropic Managed Agents bash tool surface.
        """
        ctx.deps.bash_calls += 1
        n = ctx.deps.bash_calls
        ds = ctx.deps.dataset_id[:8]
        if not command:
            log.info(
                "test[%s]: bash#%d empty call (restart=%s) — raising ModelRetry",
                ds, n, restart,
            )
            raise ModelRetry(
                "bash requires a non-empty `command` parameter. The sandbox "
                "is persistent — there is nothing to restart. If you have "
                "completed all investigation and written "
                "/tmp/session/outputs/content.html and agent_data.json, end "
                "the run by returning a final assistant message instead of "
                "calling a tool."
            )
        log.info("test[%s]: bash#%d $ %s", ds, n, _summarize_arg(command))
        t0 = time.monotonic()
        out = _exec_to_dict(ctx.deps.sandbox.run_code(command, language="bash", timeout=120))
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


def _extract_openrouter_cost(messages: list) -> Optional[float]:
    """Sum the actual billed USD across all model responses in a run.

    With usage accounting enabled, OpenRouter reports per-request cost in
    credits (1 credit = 1 USD); PydanticAI's OpenRouterModel surfaces it
    as `ModelResponse.provider_details['cost']`. Returns None when no
    response carried a cost (e.g. non-OpenRouter run).
    """
    total = 0.0
    seen = False
    for m in messages:
        details = getattr(m, "provider_details", None)
        if isinstance(details, dict) and details.get("cost") is not None:
            total += float(details["cost"])
            seen = True
    return round(total, 6) if seen else None


def _compute_cost(*, model: str, usage: dict[str, int], messages: list) -> dict[str, Any]:
    actual = _extract_openrouter_cost(messages)
    if actual is not None:
        return {
            "tokens_usd": actual,
            "total_usd": actual,
            "cost_source": "openrouter",
        }
    prices = PRICE_TABLE.get(model)
    if prices is None:
        return {
            "tokens_usd": None,
            "total_usd": None,
            "cost_source": None,
            "note": "no OpenRouter cost in responses and model not in PRICE_TABLE",
        }
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
        "cost_source": "price_table",
    }


@dataclass
class AgentSessionOutput:
    """Raw result of one agent session — not yet validated or persisted."""
    content_html_raw: str
    agent_data_raw: bytes
    usage: dict[str, int]
    cost: dict[str, Any]
    iterations: int
    tool_calls: dict[str, int]
    messages: list
    elapsed_seconds: float


def run_agent_session(
    *,
    sandbox,
    model: str,
    dataset_id: str,
    title: str,
    notes: str,
    org_title: str,
    primary_resource_id: Optional[str],
    outputs_dir: str,
    check_script: str,
    pre_fetched_schema: Optional[dict] = None,
) -> AgentSessionOutput:
    """Drive one agent session on an already-created sandbox.

    Shared by production (`agent_runner`, LocalSandbox) and the local
    test harness (`run_test_session`, PodmanSandbox). Provisions
    check.py at `check_script`, runs the PydanticAI loop, and returns
    the RAW outputs + telemetry — validation, sanitizing, and
    persistence are the caller's responsibility.
    """
    system_prompt = _load_system_prompt()
    user_msg = build_user_message(
        dataset_id=dataset_id,
        title=title,
        notes=notes,
        org_title=org_title,
        primary_resource_id=primary_resource_id,
        outputs_dir=outputs_dir,
        check_script=check_script,
        pre_fetched_schema=pre_fetched_schema,
    )
    httpx_client = httpx.Client()
    deps = Deps(sandbox=sandbox, httpx_client=httpx_client, dataset_id=dataset_id)
    started = time.monotonic()
    try:
        _provision_check_script(sandbox, check_script)
        py_model, model_settings = _build_pydantic_model(model)
        agent = _build_agent(
            model=py_model, system_prompt=system_prompt, model_settings=model_settings
        )
        log.info("session[%s]: agent.run_sync model=%s", dataset_id[:8], model)
        result = agent.run_sync(user_msg, deps=deps)
        elapsed = time.monotonic() - started

        od = outputs_dir.rstrip("/")
        try:
            content_html_bytes = sandbox.files.read(f"{od}/{CONTENT_FILENAME}")
            agent_data_bytes = sandbox.files.read(f"{od}/{AGENT_DATA_FILENAME}")
        except Exception as e:
            raise RuntimeError(
                f"agent did not produce both output files: {e}"
            ) from e
    finally:
        try:
            httpx_client.close()
        except Exception:
            pass

    messages = result.all_messages()
    usage = _extract_usage(result.usage)
    iterations = sum(
        1 for m in messages
        if hasattr(m, "parts") and any(
            type(p).__name__ in ("ToolCallPart", "ToolReturnPart") for p in m.parts
        )
    )
    return AgentSessionOutput(
        content_html_raw=(
            content_html_bytes.decode("utf-8")
            if isinstance(content_html_bytes, (bytes, bytearray))
            else str(content_html_bytes)
        ),
        agent_data_raw=(
            bytes(agent_data_bytes)
            if isinstance(agent_data_bytes, (bytes, bytearray))
            else str(agent_data_bytes).encode("utf-8")
        ),
        usage=usage,
        cost=_compute_cost(model=model, usage=usage, messages=messages),
        iterations=iterations,
        tool_calls={
            "bash": deps.bash_calls,
            "code_execution": deps.code_calls,
            "web_fetch": deps.fetch_calls,
            "web_search": deps.search_calls,
        },
        messages=messages,
        elapsed_seconds=round(elapsed, 2),
    )


def run_test_session(
    *,
    dataset_id: str,
    title: str,
    notes: str,
    org_title: str,
    primary_resource_id: Optional[str],
    out_dir: Path,
    model: str,
    max_iters: int = 30,  # noqa: ARG001 - PydanticAI controls retries; kept for caller parity
) -> TestSessionResult:
    """Local test run: Podman sandbox, artifacts written to `out_dir`.

    Manual-run only — never imported by production code.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    from .podman_sandbox import PodmanSandbox

    log.info("test[%s]: starting Podman sandbox + model=%s", dataset_id[:8], model)
    sandbox = PodmanSandbox.create()
    try:
        out = run_agent_session(
            sandbox=sandbox,
            model=model,
            dataset_id=dataset_id,
            title=title,
            notes=notes,
            org_title=org_title,
            primary_resource_id=primary_resource_id,
            outputs_dir=OUTPUTS_DIR_IN_SANDBOX,
            check_script=CHECK_SCRIPT_IN_SANDBOX,
        )
        sandbox_files: list[str] = []
        try:
            for entry in sandbox.files.list(OUTPUTS_DIR_IN_SANDBOX):
                sandbox_files.append(getattr(entry, "name", str(entry)))
        except Exception:
            pass
    finally:
        try:
            sandbox.kill()
        except Exception as e:
            log.warning("test[%s]: sandbox.kill failed: %s", dataset_id[:8], e)

    content_html = sanitize_content_html(out.content_html_raw, dataset_id=dataset_id)
    agent_data = AgentData.model_validate_json(out.agent_data_raw)

    content_html_path = out_dir / CONTENT_FILENAME
    agent_data_path = out_dir / AGENT_DATA_FILENAME
    transcript_path = out_dir / "transcript.json"
    cost_path = out_dir / "cost.json"

    content_html_path.write_text(content_html, encoding="utf-8")
    agent_data_path.write_text(
        json.dumps(agent_data.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    transcript_path.write_text(
        json.dumps(_serialize_messages(out.messages), ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    cost_path.write_text(
        json.dumps(
            {
                "model": model,
                "elapsed_seconds": out.elapsed_seconds,
                "usage": out.usage,
                "cost_usd": out.cost,
                "tool_calls": out.tool_calls,
                "sandbox_files": sandbox_files,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return TestSessionResult(
        dataset_id=dataset_id,
        model=model,
        out_dir=out_dir,
        content_html_path=content_html_path,
        agent_data_path=agent_data_path,
        transcript_path=transcript_path,
        cost_path=cost_path,
        iterations=out.iterations,
        elapsed_seconds=out.elapsed_seconds,
        usage=out.usage,
        cost_usd=out.cost,
        sandbox_files=sandbox_files,
    )
