---
name: govdata-design
description: |
  Design system + body-content contract for GovData.IL dataset pages. Load
  when authoring a per-dataset content.html + agent_data.json. The page
  chrome (header, nav, breadcrumb, related sidebar, footer) is injected by
  a Python wrapper — this skill describes ONLY what you write, and the
  design tokens available to you inside the wrapper's shell. Tokens mirror
  www.gov.il so the output looks native.
---

# GovData.IL — Body-Content Design Skill

You write the **main content body** for one dataset page. The Python
wrapper already includes the site shell: shared head (fonts, Tailwind,
meta), header + nav, breadcrumb, related-datasets sidebar, footer.
Don't duplicate any of that.

## What you write

**`/mnt/session/outputs/content.html`** — content that goes inside a
`<main>` container sized by the wrapper (`max-w-gov mx-auto px-4 py-8`).

Must include (in this order, roughly):

1. `<h1>` — dataset title.
2. Tag chips — `<div class="flex flex-wrap gap-2 mb-4"><span class="tag-chip">…</span>…</div>`.
3. AI summary card — 2–3 sentences in a `<section class="card p-5 mb-4">` with a confidence badge.
4. Metadata + Resources — two cards side by side (grid).
5. Insights — a `<ul>` of as many bullets as the data genuinely supports (1 minimum, no upper cap). Don't pad with filler — a thin dataset with one real finding gets one bullet.
6. **Data Explorer** — your visualizations, each in a `<section class="card p-5 mb-5">`.
7. Original notes (CKAN `notes` verbatim) in a `<section>`.

**DO NOT** include `<html>`, `<head>`, `<body>`, a site `<header>` nav,
breadcrumb, or footer. The wrapper owns those.

**`<style>` tags** inside content.html are fine — they apply globally
but in practice the wrapper's Tailwind-first approach means you rarely
need custom CSS beyond viz-library defaults.

**`<script>` tags** inside content.html — inline only, no `src=`.
The shell pre-loads ECharts / Leaflet / MarkerCluster in `<head>` so
the globals are available to your inline init code by the time the
body parses.

## Design tokens (already loaded by the wrapper)

- **Font**: Rubik, loaded from Google Fonts (weights 300/400/500/600/700).
  Applies to both body text and headings. Do not load Heebo.
- **Body**: `font-size: 1rem`, `line-height: 1.5` (not 1.7).
- **Headings**: font-weight 500, line-height 1.2. Use the plain
  `<h1>`/`<h2>`/`<h3>` elements — the wrapper's `@layer base` applies
  gov.il's fluid `clamp()` sizes automatically.

Colors (Tailwind classes or raw hex):

| Token | Class | Hex |
|-------|-------|-----|
| primary | `bg-brand` / `text-brand` / `border-brand` | `#0068f5` |
| primary hover | `hover:bg-brand-600` | `#0053c4` |
| ink (body text) | `text-ink` | `#0c3058` |
| surface (page bg) | `bg-surface` | `#f1f7ff` |
| surface-alt | `bg-surface-alt` | `#f0f4fa` |
| rule (border) | `border-rule` | `#c3cfe7` |
| subtle (muted) | `text-subtle` | `#6c757d` |
| success | `text-ok` / `bg-ok` | `#198754` |
| warning | `text-warn` / `bg-warn` | `#ffc107` |
| danger | `text-danger` / `bg-danger` | `#dc3545` |
| info | `text-info` / `bg-info` | `#0dcaf0` |

Radii:

| Class | Value | Use |
|-------|-------|-----|
| `rounded-gov-sm` | 0.2rem | badges |
| `rounded-gov-md` | 0.3rem | compact controls |
| `rounded-gov` | 0.5rem | cards, buttons |
| `rounded-gov-pill` | 50rem | chips, pills |

Component utilities the wrapper defines:

- `.card` — white bg, `border-rule`, `rounded-gov` (8px), subtle
  shadow. Pair with `.card-hover` for the hover lift.
- `.tag-chip` — pill for tags (blue text on light-blue bg).
- `.badge` — neutral small pill for org/format chips.
- `.btn-primary` — solid brand-blue button.
- `.btn-ghost` — outlined brand-blue button.

`<html dir="rtl" lang="he">` is already set by the wrapper.

## Icon set

The wrapper ships a curated Lucide-based SVG set under `/icons/`. You
can reference them with `<img src="/icons/<name>.svg" alt="" class="w-5 h-5" />`
or inline the SVG to color via `currentColor` (preferred for sidebars).

Available:

| Name | Use |
|------|-----|
| `search` | search fields, filter bars |
| `arrow-left` / `arrow-right` | nav buttons, "continue" affordances |
| `chevron-left` / `chevron-right` | breadcrumbs, pagination |
| `external-link` | links to data.gov.il / outside sources |
| `download` | resource download buttons |
| `database` | dataset / primary-resource callouts |
| `building-2` | ministry callouts |
| `tag` | tag rows |
| `map-pin` | geographic datasets |
| `list` | registry / tabular datasets |
| `info` | explainer callouts |
| `circle-check` | success, confidence-high |
| `triangle-alert` | warnings, low-confidence |

SVGs are stroke-based (`stroke-width: 1.75`, `stroke="currentColor"`).
Default size 20–24px. Do not introduce other icon libraries.

## Visualization guidelines

Pick libraries per dataset; there is no fixed taxonomy. Common fits:

| `dataset_kind` | Libraries to reach for                              |
| -------------- | --------------------------------------------------- |
| map            | Leaflet + OSM tiles; MarkerCluster if >200 points   |
| timeseries     | ECharts line / area (RTL-friendly)                  |
| registry       | Custom table + ECharts bar for a column breakdown   |
| rankings       | ECharts horizontal bar                              |
| misc           | Pick what the data shape suggests (ECharts covers   |
|                | sunburst, treemap, graph/force-directed, heatmap)   |

Available globals (pre-loaded by the shell — these are the tools,
use them):

| Global | Library | Use for |
|--------|---------|---------|
| `echarts` | ECharts | every chart kind: bar / line / pie / sunburst / treemap / heatmap / radar |
| `L` | Leaflet | maps + tiles |
| `L.markerClusterGroup` | Leaflet.markercluster | clustering when >200 points |

Do NOT write `<script src=…>` or `<link rel="stylesheet" href=…>` to
load anything. Tailwind, Rubik, and the viz libs above are already
loaded by the shell; your `content.html` only needs inline init code.

### Categorical palette — use on every chart

Copy this into a `<script>` block near the top of `content.html`:

```js
const GOVIL_PALETTE = [
  '#0068f5', '#0b3668', '#6c9fd8', '#0053c4', '#0c3058',
  '#3d70b0', '#b7d2f7', '#2658a0', '#dbe8fb', '#0c1f3d'
];
```

Every chart's `color:` MUST come from this array. Do not let ECharts /
Chart.js fall back to their multi-hue defaults. Reserve `#198754`
(ok), `#ffc107` (warn), `#dc3545` (danger), `#0dcaf0` (info) for true
semantic meaning only — never as categorical fill.

Forbidden: Bootstrap-ish `#6f42c1` (purple), `#856404` (amber),
`#fd7e14` (orange), `#e83e8c` (pink), `#20c997` (teal), `#6610f2`
(violet), `#d63384` (magenta), and any Tailwind default like
`#8b5cf6` (violet-500).

### ECharts RTL + Rubik preset

```js
const baseECharts = {
  color: GOVIL_PALETTE,
  textStyle: { fontFamily: 'Rubik, sans-serif', color: '#0c3058' },
  tooltip: {
    textStyle: { fontFamily: 'Rubik', color: '#0c3058' },
    backgroundColor: '#fff',
    borderColor: '#c3cfe7',
    extraCssText: 'direction: rtl; box-shadow: 0 6px 24px -8px rgba(0,104,245,.18);'
  },
  grid: { left: 48, right: 64, top: 40, bottom: 48, containLabel: true },
};

// Every chart instance:
const option = Object.assign({}, baseECharts, {
  xAxis: { ... }, yAxis: { ... }, series: [ ... ],
});
```

### Leaflet RTL caveats

The wrapper already injects:

```css
.leaflet-container     { direction: ltr; }
.leaflet-popup-content { direction: rtl; text-align: right; }
```

Inside popups, Hebrew flows RTL; tiles stay LTR. Convert ITM
(`EPSG:2039`) → WGS84 (`EPSG:4326`) with pyproj before embedding
`[lat, lng]` arrays in JS.

## Reference content.html skeleton

This is the exact shape a new page should start from. Note: no
`<!DOCTYPE>`, no `<html>/<head>/<body>`, no font or Tailwind `<link>`
(the wrapper owns those), no outer `max-w-*` utility (the wrapper
sizes you to `max-w-gov` already).

```html
<!-- tag chips -->
<h1>שם המאגר</h1>
<div class="flex flex-wrap gap-2 mb-4">
  <span class="tag-chip">תגית-1</span>
  <span class="tag-chip">תגית-2</span>
</div>

<!-- AI summary card -->
<section class="card p-5 mb-4">
  <div class="flex items-center justify-between mb-2">
    <h2 class="m-0 text-base font-display">תקציר</h2>
    <span class="badge inline-flex items-center gap-1">
      <img src="/icons/circle-check.svg" alt="" class="w-4 h-4 text-ok" />
      ודאות גבוהה
    </span>
  </div>
  <p class="m-0 text-subtle">שני עד שלושה משפטים בעברית, המתארים את המאגר…</p>
</section>

<!-- metadata + resources: rendered by the Nuxt shell (frontend/pages/datasets/[id].vue)
     from data.json (organization, license, last-updated, record_count, downloads).
     The publisher writes data.json from the scanner's Firestore record — you do NOT
     emit any of those fields in agent_data.json or in content.html. -->

<!-- insights -->
<section class="card p-5 mb-4">
  <h2 class="m-0 mb-3 text-base font-display">תובנות</h2>
  <ul class="m-0 ps-5 space-y-2 text-sm">
    <li>המדידה הנמוכה ביותר: <span dir="ltr">−440.79 מ'</span> (מרץ 2026).</li>
    <li>קצב הירידה הממוצע: כ-0.84 מ' לשנה.</li>
  </ul>
</section>

<!-- data explorer -->
<section class="card p-5 mb-5">
  <h2 class="m-0 mb-3 text-base font-display">חקר הנתונים</h2>
  <div id="chart-main" class="h-80"></div>
</section>

<!-- original notes -->
<section class="card p-5 mb-4">
  <h2 class="m-0 mb-2 text-base font-display">תיאור מקורי</h2>
  <p class="m-0 text-sm text-subtle whitespace-pre-line">…</p>
</section>

<script>
  const GOVIL_PALETTE = [ /* ...copy from above... */ ];
  const baseECharts  = { /* ...copy from above... */ };
  const chart = echarts.init(document.getElementById('chart-main'));
  chart.setOption(Object.assign({}, baseECharts, {
    xAxis: { type: 'category', data: ['א','ב','ג'] },
    yAxis: { type: 'value' },
    series: [{ type: 'bar', data: [120, 200, 150] }],
  }));
  window.addEventListener('resize', () => chart.resize());
</script>
```

## `agent_data.json` contract

The agent writes ONLY interpretive fields. Everything factual (id, title,
slug, organization, license, resources, formats, record_count,
metadata_modified) is owned by the scanner and merged in by the
publisher — do not emit those.

```json
{
  "summary_he": "<one-line hebrew summary>",
  "dataset_kind": "map" | "timeseries" | "registry" | "rankings" | "misc",
  "related_ids": ["<id>", "<id>", "<id>"],
  "version": 1
}
```

`summary_he` — required. One concise Hebrew sentence (or two if the
domain genuinely needs it). Same content as the AI summary card in
content.html, but as plain text — the frontend uses this for SEO meta
tags and home-page cards.

`dataset_kind` — required. Drives the `/kinds/<kind>/` route and a few
icon/label choices on cards.

`related_ids` — up to 5 dataset IDs you think are topically related.
Return `[]` if you don't have enough context. The publisher merges your
suggestions with deterministic scoring (ministry + shared tags +
embedding similarity).

## Accessibility + SEO

- `alt` text on all images.
- Interactive viz controls keyboard-reachable.
- `<h1>` exactly once per page (yours).
- Do not include `<title>`, `<meta name="description">`, or OG tags —
  the wrapper generates those from `data.json` + `agent_data.json`.

## Do not

- Do not add `<html>`, `<head>`, `<body>`.
- Do not add your own header/nav/breadcrumb/related-sidebar/footer.
- Do not `<link>` fonts or Tailwind — the wrapper loads them.
- Do not set a `max-w-*` utility on your top-level container. The
  wrapper already sizes you via `max-w-gov` (1400px). You may use
  `max-w-*` on inner prose columns that need to be narrower.
- Do not use Tailwind's default purple/indigo accents.
- Do not use the Israeli flag colors (`#0038B8` etc.) — we use
  gov.il's own blue `#0068f5`, which is distinct.
- Do not set `line-height: 1.7` on body or paragraphs — gov.il uses
  1.5. If Hebrew-heavy prose feels tight, bump *that paragraph* to
  `leading-relaxed` (1.625), not the whole doc.
- Do not generate emoji in government content.
- Do not override the card radius (`rounded-gov` = 0.5rem / 8px). No
  `rounded-xl` or `rounded-2xl`.
- Do not load Heebo, Open Sans Hebrew, or any font other than Rubik.
