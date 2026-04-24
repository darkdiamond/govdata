import manifestData from '~/public/data/manifest.json'
import type { Manifest, ManifestEntry } from '~/types/manifest'

// Read the manifest at build time — SSG needs every route resolvable during
// prerender, before the static output is served. If you change
// public/data/manifest.json you must rebuild the site.
const _manifest = manifestData as unknown as Manifest

export function useManifest() {
  return computed(() => _manifest)
}

export function useFacets(entries: ManifestEntry[]) {
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
