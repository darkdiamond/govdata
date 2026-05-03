"""Tests for the agent-output sanitizer in session_runner.

Catches the recurring LLM hallucination modes that broke
dataset 27b4b40e-…: fabricated SRI hashes on Leaflet, JSON-escaped
script-end tags (`<\\/script>`), and any `<script src=CDN>` /
`<link href=CDN>` references the agent prompt now forbids.

Run directly: `python -m services.page_builder.tests.test_session_runner_sanitize`
Or via pytest if available.
"""
from __future__ import annotations

import logging

from services.page_builder.session_runner import _sanitize_content_html


def _logs(caplog_or_none, *, dataset_id="x", body):
    logger = logging.getLogger("services.page_builder.session_runner")
    records: list[logging.LogRecord] = []

    class H(logging.Handler):
        def emit(self, record):
            records.append(record)

    h = H()
    logger.addHandler(h)
    try:
        return _sanitize_content_html(body, dataset_id=dataset_id), records
    finally:
        logger.removeHandler(h)


def test_replaces_escaped_script_end_tag() -> None:
    src = '<script src="/lib/x.js"><\\/script>\n<script>alert(1);<\\/script>'
    out, recs = _logs(None, body=src)
    assert "<\\/script>" not in out
    assert out.count("</script>") == 2
    assert any("</script>" in r.getMessage() for r in recs)


def test_strips_integrity_and_crossorigin() -> None:
    src = (
        '<script src="https://unpkg.com/leaflet/leaflet.js" '
        'integrity="sha256-bad" crossorigin=""></script>\n'
        '<link rel="stylesheet" href="/lib/leaflet.css" '
        'integrity="sha256-bad2" crossorigin>'
    )
    out, recs = _logs(None, body=src)
    assert "integrity=" not in out
    assert "crossorigin" not in out
    msgs = " ".join(r.getMessage() for r in recs)
    assert "integrity" in msgs
    assert "crossorigin" in msgs


def test_drops_cdn_script_and_link_tags() -> None:
    src = (
        '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>\n'
        '<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>\n'
        '<link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css">\n'
        '<script>echarts.init(...)</script>'
    )
    out, recs = _logs(None, body=src)
    assert "unpkg.com" not in out
    assert "jsdelivr" not in out
    # Inline script kept.
    assert "echarts.init" in out
    msgs = " ".join(r.getMessage() for r in recs)
    assert "<script src=CDN>" in msgs
    assert "<link href=CDN>" in msgs


def test_clean_input_pass_through_no_warnings() -> None:
    src = (
        '<h1>Title</h1>\n'
        '<div id="map" class="h-80"></div>\n'
        '<script>const m = L.map("map");</script>\n'
        '<script>echarts.init(document.getElementById("c"));</script>'
    )
    out, recs = _logs(None, body=src)
    assert out == src
    # No sanitizer rule should fire on already-clean input.
    assert not [r for r in recs if "sanitizer:" in r.getMessage()]


def test_does_not_drop_local_lib_scripts() -> None:
    """Non-CDN script srcs (like our own /lib/) must be left alone."""
    src = '<script src="/lib/echarts.min.js"></script>\n<script>x</script>'
    out, _ = _logs(None, body=src)
    assert out == src


def test_real_world_27b4b40e_pattern() -> None:
    """The exact failure mode we hit on dataset 27b4b40e-…: bad SRI +
    escaped script-end tags. After sanitize, both classes are gone."""
    src = (
        '<link rel="stylesheet" '
        'href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" '
        'integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" '
        'crossorigin="" />\n'
        '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" '
        'integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV/XN/WLs=" '
        'crossorigin=""><\\/script>\n'
        '<script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js" '
        'crossorigin=""><\\/script>\n'
        '<script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"><\\/script>\n'
        '<script>const map = L.map("map");<\\/script>'
    )
    out, _ = _logs(None, body=src)
    assert "<\\/script>" not in out
    assert "integrity=" not in out
    assert "crossorigin" not in out
    assert "unpkg.com" not in out
    assert "jsdelivr" not in out
    # The inline init script is preserved (with proper </script> close).
    assert 'L.map("map")' in out
    assert out.count("</script>") == 1


def test_balances_unclosed_script_tag() -> None:
    """Real failure mode from dataset e4a5e2d7-…: an inline <script>
    opened but never closed swallows the rest of the document. Sanitizer
    must append the missing </script>."""
    src = '<h1>x</h1>\n<script>\n(function(){console.log(1);})();\n'
    out, recs = _logs(None, body=src)
    assert out.count("<script") == 1
    assert out.count("</script>") == 1
    msgs = " ".join(r.getMessage() for r in recs)
    assert "appended 1 missing </script>" in msgs


def test_balances_two_unclosed_scripts() -> None:
    src = (
        '<script>(function(){a();})();\n'
        '<script>(function(){b();})();\n'
    )
    out, _ = _logs(None, body=src)
    assert out.count("<script") == 2
    assert out.count("</script>") == 2


def test_balances_unclosed_style_tag() -> None:
    src = '<style>.x{color:red;}\n<h1>title</h1>'
    out, recs = _logs(None, body=src)
    assert out.count("<style") == 1
    assert out.count("</style>") == 1
    msgs = " ".join(r.getMessage() for r in recs)
    assert "appended 1 missing </style>" in msgs


def test_balanced_input_unchanged() -> None:
    src = '<script>x</script>\n<style>.a{}</style>'
    out, recs = _logs(None, body=src)
    assert out == src
    assert not [r for r in recs if "appended" in r.getMessage()]


def test_commented_out_script_does_not_count() -> None:
    """An <!-- <script> --> comment must not be treated as an opener."""
    src = '<!-- <script>old</script> -->\n<script>x</script>'
    out, recs = _logs(None, body=src)
    assert out == src
    assert not [r for r in recs if "appended" in r.getMessage()]


def test_stray_close_script_warns_but_unchanged() -> None:
    src = '<p>hi</p></script>'
    out, recs = _logs(None, body=src)
    assert out == src
    msgs = " ".join(r.getMessage() for r in recs)
    assert "stray" in msgs


def test_excess_unclosed_scripts_raises() -> None:
    """If the body is structurally broken (more than the cap of unclosed
    scripts), refuse to publish — a string-append won't safely repair it."""
    import pytest  # type: ignore
    src = "<script>a\n<script>b\n<script>c\n<script>d\n<script>e\n<script>f\n"
    try:
        _sanitize_content_html(src)
    except ValueError as e:
        assert "exceeds auto-repair cap" in str(e)
    else:
        raise AssertionError("expected ValueError for excess unclosed scripts")


def test_real_world_e4a5e2d7_pattern() -> None:
    """Exact failure shape from dataset e4a5e2d7-…: the inline ECharts
    IIFE is the only <script>, it never gets closed, and the file ends
    on `})();\\n`. After sanitize there must be a matching </script>."""
    src = (
        '<h1>title</h1>\n'
        '<div id="chart-monthly"></div>\n'
        '<script>\n'
        '(function(){\n'
        '  const el = document.getElementById("chart-monthly");\n'
        '  echarts.init(el).setOption({});\n'
        '})();\n'
    )
    out, _ = _logs(None, body=src)
    assert out.count("<script") == 1
    assert out.count("</script>") == 1
    # The IIFE itself must still be intact.
    assert 'echarts.init' in out


def main() -> None:
    tests = [
        test_replaces_escaped_script_end_tag,
        test_strips_integrity_and_crossorigin,
        test_drops_cdn_script_and_link_tags,
        test_clean_input_pass_through_no_warnings,
        test_does_not_drop_local_lib_scripts,
        test_real_world_27b4b40e_pattern,
        test_balances_unclosed_script_tag,
        test_balances_two_unclosed_scripts,
        test_balances_unclosed_style_tag,
        test_balanced_input_unchanged,
        test_commented_out_script_does_not_count,
        test_stray_close_script_warns_but_unchanged,
        test_excess_unclosed_scripts_raises,
        test_real_world_e4a5e2d7_pattern,
    ]
    for t in tests:
        t()
        print(f"  ok  {t.__name__}")
    print(f"\n{len(tests)} tests passed")


if __name__ == "__main__":
    main()
