---
name: govdata-design
description: |
  Design system + body-content contract for GovData.IL dataset pages. Load
  when authoring a per-dataset content.html + data.json. The page chrome
  (header, nav, breadcrumb, related sidebar, footer) is injected by a
  Python wrapper — this skill describes ONLY what you write, and the design
  tokens available to you inside the wrapper's shell.
---

# GovData.IL — Body-Content Design Skill

You write the **main content body** for one dataset page. The Python wrapper
already includes the site shell: shared head (fonts, Tailwind, meta),
header + nav, breadcrumb, related-datasets sidebar, footer. Don't duplicate
any of that.

## What you write

**`/mnt/session/outputs/content.html`** — content that goes inside a
`<main class="max-w-6xl mx-auto px-4 py-8">` container on the final page.

Must include (in this order, roughly):

1. `<h1>` — dataset title.
2. Tag chips — `<div class="flex flex-wrap gap-2 mb-4"><span class="tag-chip">…</span>…</div>`.
3. AI summary card — 2–3 sentences in a `<section class="card p-5 mb-4">` with a confidence badge.
4. Metadata + Resources — two cards side by side (grid).
5. Insights — a `<ul>` of 1–3 bullets.
6. **Data Explorer** — your visualizations, each in a `<section class="card p-5 mb-5">`.
7. Original notes (CKAN `notes` verbatim) in a `<section>`.
8. Quality bar — simple progress bar using the accent color.

**DO NOT** include `<html>`, `<head>`, `<body>`, a site `<header>` nav,
breadcrumb, or footer. The wrapper owns those.

**`<style>` tags** inside content.html are fine — they apply globally but
in practice the wrapper's Tailwind-first approach means you rarely need
custom CSS beyond viz-library defaults.

**`<script>` tags** inside content.html — also fine. The wrapper will
inject them at the end of `<body>` so libraries load after the DOM.

## Design tokens (already loaded by the wrapper)

- Fonts: **Heebo** (body), **Rubik** (display, h1/h2).
- Colors (Tailwind classes or CSS vars):
  - primary `#0B3D91` (`bg-brand`, `text-brand`, `border-brand`)
  - accent `#EAB308` (`bg-accent`)
  - surface `#FAFAF7` (`bg-surface`), ink `#111111` (`text-ink`),
    subtle `#6B7280` (`text-subtle`), rule `#E5E7EB` (`border-rule`)

- Utility classes the wrapper defines for you:
  - `.card` — white bg, rule border, 12px radius, subtle shadow-on-hover variant
  - `.tag-chip` — blue pill for tags
  - `.badge` — neutral pill for org + format chips

- `<html dir="rtl" lang="he">` is already set by the wrapper.

## Visualization guidelines

Pick libraries per dataset; there is no fixed taxonomy. Common fits:

| `dataset_kind` | Libraries to reach for                              |
| -------------- | --------------------------------------------------- |
| map            | Leaflet + OSM tiles; MarkerCluster if >200 points    |
| timeseries     | ECharts (RTL friendly) or Chart.js                   |
| registry       | Custom table + ECharts bar for a column breakdown    |
| rankings       | ECharts horizontal bar                               |
| misc           | Pick what the data shape suggests                    |

CDN sources (use HTTPS):
- Tailwind (already loaded; just use classes)
- Heebo / Rubik (already loaded)
- Leaflet: `https://unpkg.com/leaflet@1.9.4/dist/leaflet.css` + `.js`
- ECharts: `https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js`
- Chart.js: `https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js`
- D3: `https://cdn.jsdelivr.net/npm/d3@7`

For geo: convert ITM → WGS84 inside the container (pyproj) and embed the
converted `[lat,lng]` array inline in the page's JS. Leaflet's
`leaflet-container` element needs `direction: ltr` injected to avoid RTL
quirks — the wrapper's CSS already handles this.

## `data.json` contract

```json
{
  "id": "<dataset_id>",
  "slug": "<url-slug>",
  "title": "<title>",
  "organization": "<ministry title>",
  "organization_slug": "<pkg.organization.name from CKAN>",
  "summary_he": "<one-line hebrew summary>",
  "tags_he": ["tag1", "tag2", "tag3"],
  "primary_resource_id": "<rid>",
  "formats": ["CSV", "XLSX"],
  "metadata_modified": "<iso>",
  "dataset_kind": "map" | "timeseries" | "registry" | "rankings" | "misc",
  "related_ids": ["<id>", "<id>", "<id>"],
  "version": 1
}
```

`related_ids` — up to 3 dataset IDs you think are topically related. Return
`[]` if you don't have enough context about other datasets. The controller
merges your suggestions with deterministic scoring (shared ministry + tags)
and embedding similarity, so your picks don't have to be complete — they're
the *qualitative* signal on top of the quantitative ones.

`organization_slug` — take this directly from CKAN's `pkg.organization.name`
(it's a Latin slug like `ministry-of-justice`). It becomes the URL for the
ministry page: `/ministries/<slug>/`.

## Accessibility + SEO

- `alt` text on all images
- Interactive viz controls must be keyboard-reachable
- `<h1>` exactly once per page (yours)
- Do not include `<title>`, `<meta name="description">`, or OG tags — the
  wrapper generates those from `data.json`.

## Do not

- Do not add `<html>`, `<head>`, `<body>`.
- Do not add your own header/nav/breadcrumb/related-sidebar/footer.
- Do not use Tailwind's default purple/indigo accents.
- Do not use the Israeli flag colors.
- Do not generate emoji in government content.
