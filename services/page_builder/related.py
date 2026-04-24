"""Compute related datasets for a target entry given the manifest.

Scoring (deterministic, explainable):
    score = 5 * same_ministry
          + 2 * shared_tag_count      # capped at 6 so a very tagged dataset can't dominate
          + 3 * cosine_similarity     # only if both have an embedding
          + 4 * in_agent_suggested

We return the top K (default 5), skipping the target itself.
"""
from __future__ import annotations

import math
from typing import Iterable

from .schema import ManifestEntry

TOP_K = 5
TAG_WEIGHT = 2.0
TAG_CAP = 6
MINISTRY_WEIGHT = 5.0
EMBEDDING_WEIGHT = 3.0
AGENT_SUGGESTED_WEIGHT = 4.0


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _score(target: ManifestEntry, cand: ManifestEntry) -> tuple[float, dict]:
    signals: dict[str, float] = {}

    if (target.organization_slug and
            cand.organization_slug == target.organization_slug):
        signals["same_ministry"] = MINISTRY_WEIGHT

    shared_tags = set(target.tags_he) & set(cand.tags_he)
    if shared_tags:
        signals["shared_tags"] = TAG_WEIGHT * min(len(shared_tags), TAG_CAP)

    if target.embedding and cand.embedding:
        cos = _cosine(target.embedding, cand.embedding)
        if cos > 0.3:   # floor: only count meaningful similarity
            signals["embedding"] = EMBEDDING_WEIGHT * cos

    if cand.id in target.related_ids:
        signals["agent_suggested"] = AGENT_SUGGESTED_WEIGHT

    total = sum(signals.values())
    return total, signals


def top_related(
    target: ManifestEntry,
    candidates: Iterable[ManifestEntry],
    k: int = TOP_K,
) -> list[tuple[ManifestEntry, float, dict]]:
    """Returns up to k (candidate, score, signals) tuples, highest score first."""
    scored: list[tuple[ManifestEntry, float, dict]] = []
    for c in candidates:
        if c.id == target.id:
            continue
        total, signals = _score(target, c)
        if total <= 0:
            continue
        scored.append((c, total, signals))
    scored.sort(key=lambda t: t[1], reverse=True)
    return scored[:k]
