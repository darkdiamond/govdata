---
name: govdata-design
description: |
  Design system + body-content contract for govil.ai dataset pages. Load
  when authoring a per-dataset content.html + agent_data.json. The page
  chrome (header, nav, breadcrumb, related sidebar, footer) is injected by
  a Python wrapper — this skill describes ONLY what you write, and the
  design tokens available to you inside the wrapper's shell. Tokens mirror
  www.gov.il so the output looks native.
---

# govil.ai — Body-Content Design Skill

You write the **main content body** for one dataset page. The Python
wrapper already includes the site shell: shared head (fonts, Tailwind,
meta), header + nav, breadcrumb, related-datasets sidebar, footer.
Don't duplicate any of that.

## What you write

**`/mnt/session/outputs/content.html`** — content that goes inside a
`<main>` container sized by the wrapper (`max-w-gov mx-auto px-4 py-8`).

Must include (in this order, roughly):

1. `<h1>` — dataset title.
2. Tag chips — `<div class="flex flex-wrap gap-2 mb-6"><span class="tag-chip">…</span>…</div>`.
3. AI summary card — 2–3 sentences in a `<section class="card p-5 mb-6">`.
4. Metadata + Resources — two cards side by side (grid).
5. Insights — a `<ul>` of as many bullets as the data genuinely supports (1 minimum, no upper cap). Don't pad with filler — a thin dataset with one real finding gets one bullet.
6. **Data Explorer** — your visualizations, each in a `<section class="card p-5 mb-6">`.
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
- **Body**: `font-size: 1rem`, `line-height: 1.5` (not 1.7). If a Hebrew-
  heavy paragraph genuinely needs more breathing room, add the Tailwind
  `leading-relaxed` (1.625) utility on that paragraph — never inline
  `style="line-height: …"`.
- **Headings**: font-weight 500, line-height 1.2. Use the plain
  `<h1>`/`<h2>`/`<h3>` elements — the wrapper's `@layer base` applies
  gov.il's fluid `clamp()` sizes automatically.
- **Spacing rhythm** (single canonical rule — every page should feel the same):
  - Top-level blocks (every `<section class="card p-5">` AND any
    between-card grids like the KPI row) separate with `mb-6`.
    Never `mb-4` or `mb-5` on a top-level block.
  - Inside a card: `mb-3` for heading→body, `mb-2` for tight
    sub-elements, `mb-1` for very tight numeric labels.
  - Don't reach for `mb-7`, `mb-8`, `mb-10`, etc.
- **Color**: use the Tailwind classes from the table below (`text-danger`,
  `text-ok`, `text-ink-deep`, etc.). Never inline `style="color: #…"`.
  Semantic colors (`ok`/`warn`/`danger`/`info`) stay reserved for semantic
  meaning, not categorical fills.

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
| map            | `GovMap` for point sets (paginates CKAN at runtime, ITM→WGS84 in JS); raw Leaflet only for choropleths / single-point maps |
| timeseries     | ECharts line / area (RTL-friendly). Two-axis time (month × category, year × month %) → ECharts heatmap |
| registry       | Custom table + ECharts bar for a column breakdown; `GovExplorer` for >100 named entities |
| rankings       | ECharts horizontal bar                              |
| misc           | Pick what the data shape suggests (ECharts covers   |
|                | sunburst, treemap, graph/force-directed, heatmap)   |

For wide datasets (≥10 columns) or large datasets (≥10K rows), 6–10
charts that each tell a distinct story is fine — even encouraged.
A dataset with both geography and time and categories deserves the
depth. The constraint is that each chart tells a *distinct* story.

Available globals (pre-loaded by the shell — these are the tools,
use them):

| Global | Library | Use for |
|--------|---------|---------|
| `echarts` | ECharts | every chart kind: bar / line / pie / sunburst / treemap / heatmap / radar |
| `L` | Leaflet | maps + tiles |
| `L.markerClusterGroup` | Leaflet.markercluster | clustering when >200 points |
| `GovExplorer` | (in-house) | live `datastore_search`-backed search + paginated table — see "Live Data Explorer" below |
| `GovMap` | (in-house) | paginated, clustered map fed from `datastore_search`. ITM→WGS84 done inline. See "Live Map" below |

Do NOT write `<script src=…>` or `<link rel="stylesheet" href=…>` to
load anything. Tailwind, Rubik, and the viz libs above are already
loaded by the shell; your `content.html` only needs inline init code.

## Live Data Explorer

For registry-shaped datasets where users would plausibly look up a
specific row (a company, doctor, school, business, permit, place, …),
add a search + paginated table card that fetches live from the CKAN
`datastore_search` API in the browser. This turns a static "report"
page into a "look up your record" tool.

**When to use** — registry datasets with >100 rows AND distinct named
entities the public might search for.

**When to skip** — pure timeseries, aggregate / summary datasets, very
small registries (<100 rows where charts already say everything), and
datasets without a CSV / `datastore_active=true` resource.

**Globals**: `window.GovExplorer.create({...})` is pre-loaded
alongside `echarts` / `L`. Do NOT add a `<script src=>` for it.

**Canonical config snippet** (copy + adapt; place at the bottom of
your `<data-explorer>` section, after charts):

```html
<section class="card p-5 mb-6">
  <div class="flex flex-wrap items-center justify-between gap-3 mb-3">
    <h2 class="font-semibold text-ink-deep">עיון ברשימה</h2>
    <input
      id="explorer-search"
      class="gov-explorer-search"
      type="search"
      placeholder="חיפוש..."
      aria-label="חיפוש בטבלה"
    />
  </div>
  <div id="explorer"></div>
</section>
<script>
  GovExplorer.create({
    container: '#explorer',
    searchInput: '#explorer-search',
    resourceId: '<resource-uuid>',
    fields: ['<col1>', '<col2>', '<col3>', '<col4>'],
    headers: ['<header1>', '<header2>', '<header3>', '<header4>'],
    searchFields: ['<col1>', '<col2>'],
    pageSize: 50,
    sort: '_id asc',
    renderRow: function (r) {
      return [
        { text: r['<col1>'], dir: 'ltr' },
        { text: r['<col2>'] },
        { text: r['<col3>'] },
        { text: r['<col4>'], badge: r['<col4>'] === '<active>' ? 'ok' : 'mut' },
      ];
    },
  });
</script>
```

**`renderRow`** must return an array of cell descriptors, one per
column. The lib renders cells with `textContent` only — there is no
HTML-string path, so values are always XSS-safe. Each descriptor is:

| Field | Type | Use |
|-------|------|-----|
| `text` | string\|number | cell content (rendered via `textContent`) |
| `dir` | `'ltr'` \| `'rtl'` | per-cell direction (numeric IDs use `'ltr'`) |
| `align` | `'right'` \| `'left'` \| `'center'` | text alignment |
| `class` | string | extra `<td>` class names |
| `badge` | `'ok'` \| `'warn'` \| `'mut'` \| `'info'` \| `'danger'` | wraps `text` in a styled pill (matches gov.il-aligned semantic palette) |

**Field selection**: 4-6 columns max. Lead with the primary identifier
(numeric → `dir: 'ltr'`), then human name, then location/scope, then
status (use `badge`), then a key date.

**Search field selection**: free-text columns (name, address) and the
numeric ID. Skip status enums and dates — partial-match on those is
useless. `searchFields` defaults to all of `fields` if omitted.

**`pageSize`** controls how many rows render per "show more" click;
default 50. **`totalCap`** caps total rows fetched at 5000 — if a
registry is larger, the hint tells the user to use the CSV link.

**Error states are built-in**: loading skeleton, network failure
fallback (Hebrew copy pointing to the CSV download), empty-after-search
message. Don't emit your own.

**Avoid duplicating data fetching**: the Explorer fetches at runtime in
the browser. Keep your build-time bash queries focused on aggregates
and chart inputs — let the Explorer handle the row-level browsing.

## Live Map (GovMap)

For map-shaped datasets — point sets keyed by lat/lng or ITM
easting/northing — use `GovMap` instead of inlining marker
coordinates as a JS array. The lib paginates `datastore_search` in
the browser, applies the ITM→WGS84 inverse transform inline (no
pyproj at build time), and renders a clustered Leaflet layer with
RTL Hebrew popups. Built-in skeleton + network-error fallback.

**Why this matters**: pre-GovMap, map pages baked the entire point
set into HTML as JS literals — 226KB on `b2370286…` (קרקעות
מזוהמות), 63KB on `5944b454…` (עצים). Tailwind JIT scanned the
junk; first-paint parse cost was meaningful on mobile. GovMap fetches
the same rows from the same CKAN endpoint at runtime.

**Globals**: `window.GovMap.create({...})` pre-loaded alongside `L` /
`echarts` / `GovExplorer`. Do NOT add a `<script src=>` for it.

**Canonical config snippet**:

```html
<section class="card p-5 mb-6">
  <h2 class="font-semibold text-ink-deep mb-3">מפת המאגר</h2>
  <div id="map-main" class="h-72 md:h-[420px]"></div>
</section>
<script>
  GovMap.create({
    container:   '#map-main',
    resourceId:  '<resource-uuid>',
    latField:    '<lat-or-northing-col>',
    lngField:    '<lng-or-easting-col>',
    projection:  'wgs84',           // or 'itm' for EPSG:2039
    popupFields: [
      { field: '<name-col>',    label: 'שם' },
      { field: '<address-col>', label: 'כתובת' },
    ],
    popupTitleField: '<name-col>',
    cluster:    true,                // default
    totalCap:   5000,                // safety cap
  });
</script>
```

**Config**:

| Field | Type | Purpose |
|-------|------|---------|
| `container` | selector\|Element | target div (set a height via Tailwind utilities, not inline px) |
| `resourceId` | string | CKAN resource UUID |
| `latField` / `lngField` | string | column names. For ITM: `latField` = northing (Y), `lngField` = easting (X). |
| `projection` | `'wgs84'`\|`'itm'` | default `'wgs84'`. Use `'itm'` for EPSG:2039 — the lib runs the Snyder TM inverse inline (~50m accuracy across Israel, well below marker scale). |
| `popupFields` | `[{field, label}]` | rows in the RTL popup. `textContent`-only render, so values are XSS-safe. |
| `popupTitleField` | string | optional larger title at top of popup |
| `cluster` | boolean | default `true`; set `false` for sparse maps where clustering hides density |
| `totalCap` | number | default 5000; absolute cap on points fetched |
| `pageSize` | number | default 1000; CKAN page size |
| `filters` / `q` | object/string | optional `datastore_search` filters |
| `tileUrl` | string | default OSM; override only with explicit reason |
| `initialView` | `{center, zoom}` | fallback if no points load |

**When to skip**: choropleths (use raw Leaflet + GeoJSON), single-
point maps (just embed one `[lat, lng]`), polygon overlays. For
those, ITM→WGS84 with pyproj at build time is fine because the
output is small. **Never** inline a marker array of >100 items.

### ECharts heatmap (two-axis time, month × category, etc.)

When the data has two ordinal axes — month × category, year × month
percentage, district × type — a heatmap compresses what would
otherwise be 6–12 line charts. Use `GOVIL_PALETTE[0]` to
`GOVIL_PALETTE[1]` as the ramp:

```js
const heat = echarts.init(document.getElementById('chart-heat'));
heat.setOption(Object.assign({}, baseECharts, {
  tooltip: { position: 'top' },
  grid: { left: 80, right: 24, top: 32, bottom: 64, containLabel: true },
  xAxis: { type: 'category', data: months, splitArea: { show: true } },
  yAxis: { type: 'category', data: categories, splitArea: { show: true } },
  visualMap: {
    min: 0, max: maxValue,
    calculable: true,
    orient: 'horizontal', left: 'center', bottom: 8,
    inRange: { color: ['#dbe8fb', '#0068f5', '#0b3668'] },
    textStyle: { fontFamily: 'Rubik', color: '#0c3058' },
  },
  series: [{
    type: 'heatmap',
    data: cells,        // [[xIdx, yIdx, value], ...]
    label: { show: true, fontFamily: 'Rubik' },
    emphasis: { itemStyle: { shadowBlur: 8, shadowColor: 'rgba(0,104,245,.3)' } },
  }],
}));
```

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

### Hebrew unit suffixes inside chart code

Hebrew abbreviations like `מ'` (meter), `ק"ג` (kilogram), `ס"מ` (cm)
contain a geresh (`'`) or gershayim (`"`). These characters close JS
string literals. Inside an inline `<script>`, embed them in a
**double-quoted** string or escape — a single bare geresh inside a
single-quoted string closes the string early, the rest of the line
re-opens, and the whole IIFE fails to parse, silently killing every
chart on the page.

```js
// WRONG — `'` after `מ` closes the string; parser dies on next `;`
formatter: v => v.toFixed(1) + ' מ''
// RIGHT — double-quoted, or escape the geresh
formatter: v => v.toFixed(1) + " מ'"
formatter: v => v.toFixed(1) + ' מ\''
```

In HTML body text (outside `<script>`) the bare apostrophe is fine —
this rule applies only to JS string literals.

### Inlining CKAN row data as JS literals

CKAN address/name fields routinely carry embedded newlines, tabs, or
other control chars (e.g. `"מלון התעשייה\n"`, `" \nתחנת דלק"`). A raw
LF inside a `"…"`/`'…'` JS string literal is a hard syntax error —
V8 aborts the whole `<script>` block, blanking every chart and the
map. When you inline a row array, run each cell through
`JSON.stringify` (or strip control chars yourself) — never paste the
raw CKAN value into a JS literal:

```js
// WRONG — "מלון התעשייה\n" with raw LF kills the parser
const sites = [[32.06, 34.78, "מלון התעשייה
"]];
// RIGHT — JSON-encode each string field
const sites = [[32.06, 34.78, "מלון התעשייה\n"]];
```

### Leaflet RTL caveats (raw Leaflet only — for non-point overlays)

For typical point-set maps, prefer `GovMap` (see Live Map above) — it
handles RTL popups and ITM→WGS84 for you. Reach for raw Leaflet only
when GovMap doesn't fit: choropleths (GeoJSON polygons), single-point
maps, line/polygon overlays.

The wrapper already injects:

```css
.leaflet-container     { direction: ltr; }
.leaflet-popup-content { direction: rtl; text-align: right; }
```

Inside popups, Hebrew flows RTL; tiles stay LTR. For raw Leaflet with
ITM coordinates, convert to WGS84 with pyproj at build time and embed
`[lat, lng]` arrays inline — but only when the dataset is small. For
anything past ~100 points, use `GovMap` instead and avoid the inline
array entirely.

## Mobile-first layout (non-negotiable)

Most traffic is mobile. Every page must render cleanly at a 375px
viewport. Three rules:

**1. Highlight / KPI card grids — Tailwind responsive utilities only.**

```html
<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
  <div class="card p-4 text-center">…</div>
  …
</div>
```

If a count doesn't divide neatly (3 cards, 5 cards), use auto-fit:

```html
<div class="grid gap-4 mb-6"
     style="grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));">
```

Never combine a Tailwind class with a fixed inline `repeat(N, 1fr)` —
the inline style wins and overrides the responsive class:

```html
<!-- WRONG: stays 4-col on phones, breaks at 375px -->
<div class="grid grid-cols-2"
     style="grid-template-columns: repeat(4, 1fr);">
```

**2. Chart container heights — responsive Tailwind utilities.**

```html
<div id="chart-main" class="h-64 md:h-80"></div>   <!-- 256px / 320px -->
```

For maps, prefer `class="h-72 md:h-[420px]"` (288px / 420px). Always
pair with a resize listener so ECharts reflows on orientation change:

```js
window.addEventListener('resize', () => chart.resize());
```

Avoid inline `style="height: NNNpx"` — fixed pixel heights don't adapt
to phone viewports.

**3. Two-column comparison rows — collapse to one column on mobile.**

```html
<div class="grid grid-cols-1 md:grid-cols-2 gap-5">
  <div class="card p-4">…</div>
  <div class="card p-4">…</div>
</div>
```

The Nuxt shell carries a CSS backstop that collapses 3-/4-/5-column
grids and clamps inline chart heights at <640px, but the agent should
emit correct mobile markup on its own. Treat the backstop as defense
in depth, not a substitute.

## Reference content.html skeleton

This is the exact shape a new page should start from. Note: no
`<!DOCTYPE>`, no `<html>/<head>/<body>`, no font or Tailwind `<link>`
(the wrapper owns those), no outer `max-w-*` utility (the wrapper
sizes you to `max-w-gov` already).

```html
<!-- tag chips -->
<h1>שם המאגר</h1>
<div class="flex flex-wrap gap-2 mb-6">
  <span class="tag-chip">תגית-1</span>
  <span class="tag-chip">תגית-2</span>
</div>

<!-- AI summary card -->
<section class="card p-5 mb-6">
  <h2 class="m-0 mb-2 text-base font-display">תקציר</h2>
  <p class="m-0 text-subtle">שני עד שלושה משפטים בעברית, המתארים את המאגר…</p>
</section>

<!-- highlight cards (KPIs) — responsive: 2 cols on mobile, 4 on desktop -->
<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
  <div class="card p-4 text-center">
    <div class="text-3xl font-bold text-brand mb-1">74,977</div>
    <div class="text-sm text-subtle">עמותות רשומות</div>
  </div>
  <!-- 3 more cards… -->
</div>

<!-- metadata + resources: rendered by the Nuxt shell (frontend/pages/datasets/[id].vue)
     from data.json (organization, license, last-updated, record_count, downloads).
     The publisher writes data.json from the scanner's Firestore record — you do NOT
     emit any of those fields in agent_data.json or in content.html. -->

<!-- insights -->
<section class="card p-5 mb-6">
  <h2 class="m-0 mb-3 text-base font-display">תובנות</h2>
  <ul class="m-0 ps-5 space-y-2 text-sm">
    <li>המדידה הנמוכה ביותר: <span dir="ltr">−440.79 מ'</span> (מרץ 2026).</li>
    <li>קצב הירידה הממוצע: כ-0.84 מ' לשנה.</li>
  </ul>
</section>

<!-- data explorer -->
<section class="card p-5 mb-6">
  <h2 class="m-0 mb-3 text-base font-display">חקר הנתונים</h2>
  <div id="chart-main" class="h-64 md:h-80"></div>
</section>

<!-- original notes -->
<section class="card p-5 mb-6">
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

`dataset_kind` — required. Pick the FIRST matching row:

| Has lat/lng or ITM coords?                                  | → `map`        |
| Has a date axis with ≥3 distinct dates and a value series?  | → `timeseries` |
| Is a top-N / leaderboard?                                   | → `rankings`   |
| Is a registry of named entities (>100 distinct)?            | → `registry`  |
| None of the above                                           | → `misc`       |

A dataset that has BOTH geography and time is `map` — geographic
primacy is what users expect on the `/kinds/` route.

`related_ids` — aim for 2–3 IDs. Find them with one CKAN call:

```bash
curl -fsSG -H "User-Agent: Mozilla/5.0" --max-time 30 --retry 2 \
  "https://data.gov.il/api/3/action/package_search" \
  --data-urlencode "fq=organization:<org-name>" \
  --data-urlencode "rows=15" -o /tmp/related.json
```

Then in Python pick IDs (not titles, not slugs) from datasets that
share the ministry + at least one tag with this dataset, excluding
this dataset's own ID. Return up to 5. If `package_search` returns
nothing usable, return `[]` — the publisher's deterministic scoring
(ministry + shared tags + embedding similarity) still merges your
suggestions with its own signals.

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
- Do not write inline `style="line-height: …"` or `style="color: …"`
  at all. Use Tailwind utilities (`leading-relaxed`, `text-ink-deep`,
  `text-subtle`, `text-danger`, `text-ok`, `text-warn`, `text-info`).
  The only inline `style=` patterns this skill blesses are the
  `grid-template-columns: repeat(auto-fit, …)` for KPI auto-fit and
  CSS variables for chart-specific values.
- Do not flip-flop `mb-*` between sections. Top-level blocks always
  use `mb-6`; never `mb-4` or `mb-5`. The publisher's self-check
  rejects pages that violate this.
- Do not generate emoji in government content.
- Do not override the card radius (`rounded-gov` = 0.5rem / 8px). No
  `rounded-xl` or `rounded-2xl`.
- Do not load Heebo, Open Sans Hebrew, or any font other than Rubik.
