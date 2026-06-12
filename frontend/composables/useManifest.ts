import type { SlimEntry } from '~/types/manifest'

// NOTE: this file must never statically import public/data/manifest.json —
// that bundles the full 1.7MB manifest into a client chunk shipped on every
// page. Pages load data through frontend/utils/search-index.ts instead:
// server-side fs reads baked into each page's prerender payload, or an
// on-demand $fetch of the slim /data/search-index.json.

export function useFacets(entries: SlimEntry[]) {
  const orgs = new Map<string, number>()
  const formats = new Map<string, number>()
  for (const e of entries) {
    if (e.organization) orgs.set(e.organization, (orgs.get(e.organization) ?? 0) + 1)
    for (const f of e.formats) formats.set(f, (formats.get(f) ?? 0) + 1)
  }
  return {
    organizations: [...orgs.entries()].sort((a, b) => b[1] - a[1]),
    formats: [...formats.entries()].sort((a, b) => b[1] - a[1]),
  }
}
