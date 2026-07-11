"""JS-BALANCE rule in agent/skills/check.py.

The rule guards against page-killing V8 SyntaxErrors from unbalanced
delimiters in agent-emitted <script> blocks — the class that shipped a
broken live page on 2026-07-12 (an extra `}` inside a setOption call).
"""
import importlib.util
from pathlib import Path

import pytest

_CHECK_PATH = (
    Path(__file__).resolve().parents[3] / "agent" / "skills" / "check.py"
)
_spec = importlib.util.spec_from_file_location("agent_check", _CHECK_PATH)
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)


def _run(src: str):
    check.check_js_delimiter_balance([src])


def test_balanced_chart_config_passes():
    _run(
        """
        var c = echarts.init(document.getElementById('chart'));
        c.setOption(window.GovEcharts.option({
          tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
          series: [{ type: 'pie', data: [1, 2, 3] }]
        }));
        """
    )


def test_extra_closing_brace_fails():
    # The bddf37d6 incident: one stray `}` after the tooltip object.
    with pytest.raises(SystemExit):
        _run(
            """
            c.setOption(window.GovEcharts.option({
              tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' } },
              legend: { bottom: 0 }
            }));
            """
        )


def test_unclosed_paren_fails():
    with pytest.raises(SystemExit):
        _run("chart.setOption({ series: [] };")


def test_braces_in_strings_ignored():
    _run("var f = 'a } b } c'; var g = \"{{{\"; var h = `x } ${'{'} y`;")


def test_braces_in_comments_ignored():
    _run("// } } }\n/* { { */\nvar a = (1 + 2);")


def test_regex_literal_with_brackets_ignored():
    _run("var s = name.replace(/[{]/g, '').replace(/[}]/g, '');")


def test_division_is_not_regex():
    _run("var pct = (done / total) * 100; var half = total / 2;")


def test_mismatched_kind_fails():
    with pytest.raises(SystemExit):
        _run("var a = foo(bar[1)];")
