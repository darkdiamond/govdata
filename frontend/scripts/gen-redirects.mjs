#!/usr/bin/env node
// Regenerate hosting.redirects in firebase.json from the freshly published
// manifest (public/data/manifest.json), so old URLs keep 301-ing to their
// current location instead of 404-ing. Run on every deploy, after the
// publisher writes the manifest and before `firebase deploy` — the redirect
// set then never drifts from the live corpus.
//
// Two URL-scheme migrations produce durable old->new maps:
//
//   1. Dataset scheme change (commit e3c6ac7, 2026-06-23): pages moved from
//      /datasets/<CKAN-uuid>/ to /datasets/<hebrew-page_slug>/. Every current
//      dataset id -> its page_slug is a 301. Re-analysis can also change a
//      title (hence the slug), so regenerating from the live manifest — not a
//      one-time snapshot — is what keeps the 13-and-counting gaps from
//      recurring. Supersedes the manual snapshot from commit 1653950.
//
//   2. Tag slug normalization: the tag URL segment used to keep raw spaces
//      (/tags/סימני מסחר/); it now collapses whitespace to '-'
//      (/tags/סימני-מסחר/). The finite set of old space-form URLs Google
//      still holds is listed below and 301s to the dash-form when that tag
//      still exists.
//
// Deliberately NOT redirected: genuinely-removed tags and the abandoned
// Latin-transliteration tag scheme (/tags/mym/, /tags/rkb/, …). They have no
// current equivalent, and mass-redirecting gone pages to an index is a
// soft-404 pattern search engines penalise — a real 404 is the correct signal.

import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(__dirname, '..')
const REPO = resolve(ROOT, '..')

const manifestPath = resolve(ROOT, 'public/data/manifest.json')
const firebasePath = resolve(REPO, 'firebase.json')

// Old space-form tag URLs Google indexed before whitespace was normalised to
// '-'. Historical/fixed — the scheme changed once. Each maps to the dash-form
// only if that tag still exists in the corpus (else it's left to 404).
const OLD_SPACE_TAGS = [
  'סימני מסחר',
  'אתרי בנייה שנסגרו',
  'שמאים מכריעים',
  'אתרי בנייה',
  'סיווגי CPC',
  'שינויים בחברות',
  'שינויים בתאגידים',
  'מנהל הטובין',
  'משרד המשפטים',
  'אתרי בנייה פעילים',
  'שמאי מקרקעין',
  'תקנים רשמיים',
  'עיצומים כספיים',
  'עורכי פטנטים',
  'משרד העבודה',
  'רשם החברות',
  'מידע גיאוגרפי',
  'רשות המים',
  'ממציאים לבקשות פטנט',
  'בקשות פטנטים',
  'ים המלח',
  'רשימת הנוטריונים',
  'תיקי פיקוח',
]

const manifest = JSON.parse(readFileSync(manifestPath, 'utf-8'))
const datasets = manifest.datasets ?? []
const tagSlugs = manifest.tag_slugs ?? {}
const validTagSlugs = new Set(Object.values(tagSlugs))

const redirects = []

// 1. Dataset uuid -> page_slug. Source is the bare id (no trailing slash, to
//    mirror the existing block); destination is percent-encoded with a
//    trailing slash, matching how the route is prerendered.
let dsCount = 0
for (const d of datasets) {
  const slug = d.page_slug
  if (!slug || slug === d.id) continue // never exposed at a uuid URL
  redirects.push({
    source: `/datasets/${d.id}`,
    destination: `/datasets/${encodeURI(slug)}/`,
    type: 301,
  })
  dsCount++
}

// 2. Old space-form tag URL -> dash-form, when the tag still exists. Sources
//    are percent-encoded so they match the way crawlers request Hebrew paths.
let tagCount = 0
for (const t of OLD_SPACE_TAGS) {
  const dash = t.replace(/\s+/g, '-')
  if (!validTagSlugs.has(dash)) continue
  redirects.push({
    source: `/tags/${encodeURI(t)}/`,
    destination: `/tags/${encodeURI(dash)}/`,
    type: 301,
  })
  tagCount++
}

const firebase = JSON.parse(readFileSync(firebasePath, 'utf-8'))
firebase.hosting.redirects = redirects
writeFileSync(firebasePath, JSON.stringify(firebase, null, 2) + '\n', 'utf-8')

console.log(
  `[gen-redirects] wrote ${redirects.length} redirects ` +
    `(${dsCount} dataset, ${tagCount} tag) to firebase.json`,
)
