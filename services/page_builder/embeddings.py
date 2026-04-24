"""Voyage AI embeddings for dataset metadata — used to compute
relatedness across datasets.

Activates only when `VOYAGE_API_KEY` is set. If absent, returns None and
the caller falls back to ministry + tag overlap + agent suggestions only.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

log = logging.getLogger(__name__)

VOYAGE_MODEL = "voyage-3"   # Anthropic's recommended general-purpose embedder
VOYAGE_URL = "https://api.voyageai.com/v1/embeddings"


def embedding_input(title: str, summary_he: Optional[str],
                    organization: Optional[str], tags_he: list[str]) -> str:
    """Compose the text fed to the embedder. Keep this deterministic so the
    same dataset produces the same vector across runs."""
    parts = [title.strip()]
    if organization:
        parts.append(f"ארגון: {organization}")
    if summary_he:
        parts.append(summary_he)
    if tags_he:
        parts.append("תגיות: " + ", ".join(tags_he))
    return " | ".join(parts)


def embed(text: str, *, api_key: Optional[str] = None,
          timeout: float = 15.0) -> Optional[list[float]]:
    """Return a Voyage embedding vector, or None if the key isn't set / the
    call fails. We don't raise — a missing embedding just degrades the
    relatedness score; it doesn't block the publish pipeline.
    """
    api_key = api_key or os.environ.get("VOYAGE_API_KEY")
    if not api_key:
        log.info("VOYAGE_API_KEY unset — skipping embedding")
        return None
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.post(
                VOYAGE_URL,
                headers={"Authorization": f"Bearer {api_key}",
                         "Content-Type": "application/json"},
                json={"input": [text], "model": VOYAGE_MODEL},
            )
            r.raise_for_status()
            payload = r.json()
            return list(payload["data"][0]["embedding"])
    except Exception as e:
        log.warning("voyage embedding failed: %s", e)
        return None
