"""Deterministic Hebrew-aware slug helper.

URLs are routed by UUID, so the slug is purely for display/SEO and does
not need to be globally unique. Goal: stable, readable, no LLM call.
"""
from __future__ import annotations

import re
import unicodedata

# Standard Hebrew → Latin romanization. Final-form letters get the same
# value as their non-final equivalents except where the spoken sound
# differs (final kaf softens to "kh", final pe to "f").
HEBREW_TO_LATIN: dict[str, str] = {
    "א": "a",   "ב": "b",   "ג": "g",   "ד": "d",
    "ה": "h",   "ו": "v",   "ז": "z",   "ח": "ch",
    "ט": "t",   "י": "y",   "כ": "k",   "ך": "kh",
    "ל": "l",   "מ": "m",   "ם": "m",   "נ": "n",
    "ן": "n",   "ס": "s",   "ע": "a",   "פ": "p",
    "ף": "f",   "צ": "tz",  "ץ": "tz",  "ק": "k",
    "ר": "r",   "ש": "sh",  "ת": "t",
}

# Hebrew points / cantillation / punctuation we drop entirely.
_NIKTUD_RE = re.compile(r"[֑-ׇ]")
# Hebrew punctuation that should split words.
_HEB_PUNCT_RE = re.compile(r"[־׳״\"]")
# Anything that isn't a-z, 0-9, or hyphen → hyphen.
_NON_SLUG_RE = re.compile(r"[^a-z0-9-]+")
_MULTI_HYPHEN_RE = re.compile(r"-{2,}")


def slugify(text: str, *, fallback: str) -> str:
    """Return a stable, readable slug for `text`.

    Strategy:
      1. Normalize Unicode (NFC).
      2. Drop niktud / cantillation marks.
      3. Map each Hebrew letter to Latin via `HEBREW_TO_LATIN`.
      4. Lowercase any pre-existing Latin letters / digits.
      5. Replace every other character with `-`, collapse runs.
      6. If the result is empty, return `fallback` (typically the dataset id).
    """
    if not text:
        return fallback
    s = unicodedata.normalize("NFC", text)
    s = _NIKTUD_RE.sub("", s)
    s = _HEB_PUNCT_RE.sub(" ", s)

    out: list[str] = []
    for ch in s:
        mapped = HEBREW_TO_LATIN.get(ch)
        if mapped is not None:
            out.append(mapped)
        elif ch.isascii() and (ch.isalnum() or ch == "-"):
            out.append(ch.lower())
        else:
            out.append("-")
    slug = "".join(out)
    slug = _NON_SLUG_RE.sub("-", slug)
    slug = _MULTI_HYPHEN_RE.sub("-", slug).strip("-")
    return slug or fallback
