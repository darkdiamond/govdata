#!/usr/bin/env node
// Generates .output/public/sitemap.xml from public/data/manifest.json after
// `nuxt generate` completes. Listed URLs: the five static routes, every
// /ministries/<slug>/, /tags/<encoded-tag>/, /kinds/<kind>/, and every
// agent-authored /datasets/<id>/.

import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(__dirname, '..')
const SITE = 'https://gov-il.ai'

const manifestPath = resolve(ROOT, 'public/data/manifest.json')
const outPath = resolve(ROOT, '.output/public/sitemap.xml')

let manifest = { datasets: [] }
try {
  manifest = JSON.parse(readFileSync(manifestPath, 'utf-8'))
} catch {
  console.warn('[build-sitemap] no manifest.json, emitting static-only sitemap')
}

const urls = new Set([
  '/',
  '/datasets/',
  '/about/',
  '/how-it-works/',
  '/faq/',
  '/ministries/',
  '/tags/',
])

for (const d of manifest.datasets ?? []) {
  if (d.id) urls.add(`/datasets/${d.id}/`)
  if (d.organization_slug) urls.add(`/ministries/${d.organization_slug}/`)
  for (const t of d.tags_he ?? []) urls.add(`/tags/${encodeURIComponent(t)}/`)
  if (d.dataset_kind) urls.add(`/kinds/${d.dataset_kind}/`)
}

const body = [...urls]
  .sort()
  .map((u) => `  <url><loc>${SITE}${u}</loc></url>`)
  .join('\n')

const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${body}
</urlset>
`

mkdirSync(dirname(outPath), { recursive: true })
if (!existsSync(dirname(outPath))) {
  console.warn(`[build-sitemap] ${dirname(outPath)} missing — run nuxt generate first`)
  process.exit(0)
}

writeFileSync(outPath, xml, 'utf-8')
console.log(`[build-sitemap] wrote ${urls.size} URLs to ${outPath}`)
