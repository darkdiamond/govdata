"""Compute related datasets for a target entry given the manifest.

Scoring (deterministic, explainable):
    score = 1.5 * same_ministry          # tiebreaker only
          + 2   * shared_tag_count       # capped at 6 so a very tagged dataset can't dominate
          + 8   * cosine_similarity      # dominant content signal; only if both have an embedding
          + 6   * in_agent_suggested     # agent has read both pages

We return the top K (default 5), skipping the target itself.
"""
from __future__ import annotations

import math
from typing import Iterable, Optional

from .schema import ManifestEntry

TOP_K = 5
TAG_WEIGHT = 2.0
TAG_CAP = 6
MINISTRY_WEIGHT = 1.5
EMBEDDING_WEIGHT = 8.0
AGENT_SUGGESTED_WEIGHT = 6.0


def _norm(v: list[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def _cosine(
    a: list[float],
    b: list[float],
    na: Optional[float] = None,
    nb: Optional[float] = None,
) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    if na is None:
        na = _norm(a)
    if nb is None:
        nb = _norm(b)
    if na == 0 or nb == 0:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (na * nb)


def _all_tags(e: ManifestEntry) -> set[str]:
    """Union of CKAN tags (sparse, ministry-supplied) and the agent's
    `suggested_tags` (dense, editorialized). Both populate /tags/<slug>/
    pages, so both should count toward shared-tag similarity."""
    return set(e.tags_he) | set(e.suggested_tags)


def _score(
    target: ManifestEntry,
    cand: ManifestEntry,
    target_norm: Optional[float] = None,
) -> tuple[float, dict]:
    signals: dict[str, float] = {}

    if (target.organization_slug and
            cand.organization_slug == target.organization_slug):
        signals["same_ministry"] = MINISTRY_WEIGHT

    shared_tags = _all_tags(target) & _all_tags(cand)
    if shared_tags:
        signals["shared_tags"] = TAG_WEIGHT * min(len(shared_tags), TAG_CAP)

    if target.embedding and cand.embedding:
        cos = _cosine(target.embedding, cand.embedding, na=target_norm)
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
    target_norm = _norm(target.embedding) if target.embedding else 0.0
    scored: list[tuple[ManifestEntry, float, dict]] = []
    for c in candidates:
        if c.id == target.id:
            continue
        total, signals = _score(target, c, target_norm=target_norm)
        if total <= 0:
            continue
        scored.append((c, total, signals))
    scored.sort(key=lambda t: t[1], reverse=True)
    return scored[:k]
