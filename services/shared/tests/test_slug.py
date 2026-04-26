"""Tests for services.shared.slug."""
from __future__ import annotations

from services.shared.slug import slugify


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
