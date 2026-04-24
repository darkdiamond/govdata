"""Thin legacy shim — kept only so existing imports don't break.

The real write-paths now live in `session_runner` (per-session outputs) and
`manifest` (aggregated manifest). Delete this file once nothing imports it.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

log = logging.getLogger(__name__)


def fire_build_hook(hook_url: Optional[str]) -> None:
    if not hook_url:
        return
    try:
        with httpx.Client(timeout=10.0) as c:
            c.post(hook_url)
        log.info("build hook fired")
    except Exception as e:
        log.warning("build hook failed: %s", e)
