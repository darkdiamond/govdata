"""Tests for services.shared.slug."""
from __future__ import annotations

from services.shared.slug import hebrew_slugify, slugify


def test_hebrew_title_produces_non_empty_latin_slug():
    s = slugify("חברות בפרוק מרצון בהליך מזורז", fallback="dataset-id")
    assert s
    assert "-" in s
    assert all(c.isascii() for c in s)
    # No upper-case, no spaces, no leading/trailing hyphens.
    assert s == s.lower()
    assert " " not in s
    assert not s.startswith("-")
    assert not s.endswith("-")


def test_deterministic_across_calls():
    title = "רשימת שמאי מקרקעין"
    assert slugify(title, fallback="x") == slugify(title, fallback="y")


def test_empty_input_uses_fallback():
    assert slugify("", fallback="abc-123") == "abc-123"


def test_only_punctuation_uses_fallback():
    assert slugify("!!!  ?? ", fallback="abc-123") == "abc-123"


def test_strips_niktud_and_maqaf():
    # מַיִם (with niktud) and מים (without) collapse to the same slug.
    a = slugify("מַיִם", fallback="x")
    b = slugify("מים", fallback="x")
    assert a == b == "mym"


def test_handles_mixed_hebrew_and_latin():
    s = slugify("Some English Title 2024", fallback="x")
    assert s == "some-english-title-2024"


def test_collapses_runs_of_separators():
    s = slugify("חברות   בפרוק", fallback="x")
    assert "--" not in s


# --- hebrew_slugify -------------------------------------------------------

def test_hebrew_slug_keeps_hebrew_letters():
    s = hebrew_slugify("רישיונות עסק")
    assert s == "רישיונות-עסק"


def test_hebrew_slug_drops_punctuation_and_collapses():
    s = hebrew_slugify('שמאי מקרקעין (2024) — רשימה')
    assert "--" not in s
    assert not s.startswith("-") and not s.endswith("-")
    # Parentheses, year digits and the em-dash all separate words; Hebrew stays.
    assert "מקרקעין" in s and "2024" in s
    assert "(" not in s and ")" not in s


def test_hebrew_slug_strips_niktud():
    assert hebrew_slugify("מַיִם") == hebrew_slugify("מים") == "מים"


def test_hebrew_slug_keeps_final_forms():
    # Final-form letters (ך ם ן ף ץ) are inside the Hebrew block range.
    assert hebrew_slugify("ארץ") == "ארץ"


def test_hebrew_slug_empty_on_no_content():
    assert hebrew_slugify("") == ""
    assert hebrew_slugify("()-- ") == ""


def test_hebrew_slug_keeps_latin_and_digits():
    assert hebrew_slugify("GTFS feed 2024") == "GTFS-feed-2024"
