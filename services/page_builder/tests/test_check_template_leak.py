"""TEMPLATE-LEAK rule: a body must be final HTML, never an unrendered
Python str.format()/f-string template.

Two production pages (f312eda5…, 46577c12…) shipped a `content.html`
whose <script> was the *template* the agent built the HTML with — literal
`{json.dumps(...)}` placeholders and `{{`/`}}` escaped braces — instead of
the rendered result. In the browser `{json.dumps(...)}` parses as an
object literal → `Uncaught SyntaxError: Unexpected token '.'`, killing the
whole block, so no chart initialised.
"""
import importlib.util
from pathlib import Path

import pytest

_CHECK_PATH = (
    Path(__file__).resolve().parents[3] / "agent" / "skills" / "check.py"
)
_spec = importlib.util.spec_from_file_location("agent_check_tmpl", _CHECK_PATH)
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)


# ── exact shape leaked by f312eda5 ──
def test_json_dumps_placeholder_fails():
    with pytest.raises(SystemExit):
        check.check_unrendered_template(
            ["""
  (function () {{
    const cities = {json.dumps(CITIES_ASC, ensure_ascii=False)};
    const counts = {json.dumps(COUNTS_ASC)};
    const chartCities = echarts.init(document.getElementById('chart-cities'));
    chartCities.setOption(window.GovEcharts.option({{
      xAxis: {{ type: 'value', name: "מספר רבנים" }},
      series: [{{ type: 'bar', data: counts }}]
    }}));
  }})();
"""]
        )


# ── exact shape leaked by 46577c12 (var + json.dumps) ──
def test_var_json_dumps_fails():
    with pytest.raises(SystemExit):
        check.check_unrendered_template(
            ["    var years = {json.dumps(years)};\n"
             "    var counts = {json.dumps(counts)};\n"]
        )


# ── generic .format() leak with no json.dumps, only doubled braces ──
def test_format_escaped_object_fails():
    with pytest.raises(SystemExit):
        check.check_unrendered_template(
            ["""
    chart.setOption({{
      xAxis: {{ type: 'category', data: labels }},
      series: [{{ type: 'bar', data: {values} }}]
    }});
"""]
        )


# ── legitimate rendered JS must pass ──
def test_rendered_chart_passes():
    check.check_unrendered_template(
        ["""
    const cities = ["ירושלים", "בני ברק"];
    const counts = [387, 151];
    const chart = echarts.init(document.getElementById('chart-cities'));
    chart.setOption(GovEcharts.option({
      xAxis: { type: 'value' },
      yAxis: { type: 'category', data: cities },
      series: [{ type: 'bar', data: counts }]
    }));
"""]
    )


def test_empty_blocks_pass():
    check.check_unrendered_template([])
