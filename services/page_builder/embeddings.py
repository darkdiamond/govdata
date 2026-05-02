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

VOYAGE_URL = "https://api.voyageai.com/v1/embeddings"
VOYAGE_MODEL = os.environ.get("VOYAGE_MODEL", "voyage-4")


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


def embed_batch(texts: list[str], *, api_key: Optional[str] = None,
                timeout: float = 30.0) -> list[Optional[list[float]]]:
    """Embed multiple texts in one Voyage call. Returns one vector per input
    in the same order. On missing key or API failure, returns a list of
    Nones the same length as `texts` — a missing embedding only degrades
    the relatedness score, it doesn't block the publish pipeline.
    """
    if not texts:
        return []
    api_key = api_key or os.environ.get("VOYAGE_API_KEY")
    if not api_key:
        log.info("VOYAGE_API_KEY unset — skipping embedding")
        return [None] * len(texts)
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.post(
                VOYAGE_URL,
                headers={"Authorization": f"Bearer {api_key}",
                         "Content-Type": "application/json"},
                json={"input": list(texts), "model": VOYAGE_MODEL},
            )
            r.raise_for_status()
            data = r.json().get("data") or []
            ordered = sorted(data, key=lambda d: d.get("index", 0))
            return [list(d["embedding"]) for d in ordered]
    except Exception as e:
        log.warning("voyage embedding failed: %s", e)
        return [None] * len(texts)


def embed(text: str, *, api_key: Optional[str] = None,
          timeout: float = 15.0) -> Optional[list[float]]:
    """Single-text wrapper around `embed_batch` for the publish-time path."""
    out = embed_batch([text], api_key=api_key, timeout=timeout)
    return out[0] if out else None
