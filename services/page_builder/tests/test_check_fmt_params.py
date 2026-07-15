"""FMT-PARAMS rule: raw-value helpers must not be used as label formatters."""
import importlib.util
from pathlib import Path

import pytest

_CHECK_PATH = (
    Path(__file__).resolve().parents[3] / "agent" / "skills" / "check.py"
)
_spec = importlib.util.spec_from_file_location("agent_check_fmt", _CHECK_PATH)
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)


def test_named_helper_as_label_formatter_fails():
    with pytest.raises(SystemExit):
        check.check_label_formatter_params(
            ["""function numFmt(v){ return v.toLocaleString('he-IL'); }
            c.setOption({ series: [{ type: 'bar',
              label: { show: true, position: 'top', formatter: numFmt } }] });"""]
        )


def test_arrow_helper_as_label_formatter_fails():
    with pytest.raises(SystemExit):
        check.check_label_formatter_params(
            ["""const fmt = v => v.toLocaleString('he-IL');
            c.setOption({ series: [{ label: { formatter: fmt } }] });"""]
        )


def test_inline_raw_value_formatter_fails():
    with pytest.raises(SystemExit):
        check.check_label_formatter_params(
            ["""c.setOption({ series: [{ label: { show: true,
              formatter: function(v){ return v.toLocaleString('he-IL'); } } }] });"""]
        )


def test_params_aware_wrapper_passes():
    check.check_label_formatter_params(
        ["""function numFmt(v){ return v.toLocaleString('he-IL'); }
        c.setOption({ series: [{ label: { show: true,
          formatter: function(p){ return numFmt(p.value); } } }] });"""]
    )


def test_helper_used_only_for_axis_labels_passes():
    check.check_label_formatter_params(
        ["""function numFmt(v){ return v.toLocaleString('he-IL'); }
        c.setOption({ xAxis: { axisLabel: { formatter: numFmt } },
          series: [{ type: 'bar' }] });"""]
    )
