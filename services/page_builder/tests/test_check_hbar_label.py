"""HBAR-LABEL rule: horizontal-bar value labels must not sit at the bar base."""
import importlib.util
from pathlib import Path

import pytest

_CHECK_PATH = (
    Path(__file__).resolve().parents[3] / "agent" / "skills" / "check.py"
)
_spec = importlib.util.spec_from_file_location("agent_check_hbar", _CHECK_PATH)
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)


def test_hbar_label_left_fails():
    with pytest.raises(SystemExit):
        check.check_hbar_label_position(
            ["""c.setOption(GovEcharts.option({
                yAxis: { type: 'category', data: names, inverse: true },
                xAxis: { type: 'value' },
                series: [{ type: 'bar', label: { show: true, position: 'left' } }]
            }));"""]
        )


def test_hbar_label_right_passes():
    check.check_hbar_label_position(
        ["""c.setOption(GovEcharts.option({
            yAxis: { type: 'category', data: names },
            xAxis: { type: 'value' },
            series: [{ type: 'bar', label: { show: true, position: 'right' } }]
        }));"""]
    )


def test_vertical_bar_left_label_allowed():
    # No category yAxis in the block — the rule must not fire.
    check.check_hbar_label_position(
        ["""c.setOption(GovEcharts.option({
            xAxis: { type: 'category', data: names },
            yAxis: { type: 'value' },
            series: [{ type: 'bar', label: { show: true, position: 'left' } }]
        }));"""]
    )
