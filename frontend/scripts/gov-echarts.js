// gov-echarts.js — shared ECharts palette + base config for dataset
// pages. Pre-loaded by the Nuxt dataset shell (see
// frontend/utils/dataset-libs.ts) so agent-emitted content.html can
// reference `window.GOVIL_PALETTE` / `window.GovEcharts.base` without
// redefining either in every <script> block.
//
// Mirrors the design tokens documented in the agent system prompt
// (govdata-agent.yaml). If the palette or base config changes there,
// change it here too — they're the single source of truth at runtime
// and the prompt is the contract.
;(function () {
  'use strict';

  var GOVIL_PALETTE = [
    '#0068f5', '#0b3668', '#6c9fd8', '#0053c4', '#0c3058',
    '#3d70b0', '#b7d2f7', '#2658a0', '#dbe8fb', '#0c1f3d',
  ];

  var base = {
    color: GOVIL_PALETTE,
    textStyle: { fontFamily: 'Rubik, sans-serif', color: '#0c3058' },
    tooltip: {
      textStyle: { fontFamily: 'Rubik', color: '#0c3058' },
      backgroundColor: '#fff',
      borderColor: '#c3cfe7',
      extraCssText: 'direction: rtl; box-shadow: 0 6px 24px -8px rgba(0,104,245,.18);',
    },
    grid: { left: 48, right: 64, top: 40, bottom: 48, containLabel: true },
  };

  // Belt for agent-emitted horizontal bars: ECharts label positions are
  // geometric even on RTL pages, so `position: 'left'` on a
  // category-yAxis bar chart lands the value label on top of the axis
  // category names. Already-published pages carrying that mistake are
  // corrected here at render time; new pages are blocked at build time
  // by the agent self-check (HBAR-LABEL rule in check.py).
  function fixHbarLabels(o) {
    try {
      var ys = Array.isArray(o.yAxis) ? o.yAxis : o.yAxis ? [o.yAxis] : [];
      var horizontal = ys.some(function (a) { return a && a.type === 'category'; });
      if (!horizontal || !o.series) return o;
      var ss = Array.isArray(o.series) ? o.series : [o.series];
      ss.forEach(function (s) {
        if (s && s.type === 'bar' && s.label && s.label.position === 'left') {
          s.label.position = 'right';
        }
      });
    } catch (e) { /* never break a page over a label position */ }
    return o;
  }

  // Shallow-merge helper for the common pattern. Equivalent to
  // `Object.assign({}, base, override)` but reads better at the call
  // site: `chart.setOption(GovEcharts.option({xAxis, yAxis, series}))`.
  function option(override) {
    return Object.assign({}, base, fixHbarLabels(override || {}));
  }

  window.GOVIL_PALETTE = GOVIL_PALETTE;
  window.GovEcharts = { base: base, option: option };
})();
