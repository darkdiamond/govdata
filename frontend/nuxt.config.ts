// The agent owns /datasets/<id>/ as raw static HTML (served directly by the
// CDN). Nuxt only generates the home + category pages. Routes for ministries,
// tags, and kinds are enumerated from manifest.json at generate time so the
// prerender step produces one static page per category.

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

interface ManifestEntry {
  id: string
  organization_slug?: string
  tags_he?: string[]
  dataset_kind?: string
}
interface Manifest { datasets?: ManifestEntry[] }

function categoryRoutes(): string[] {
  const path = resolve(__dirname, 'public/data/manifest.json')
  let data: Manifest
  try { data = JSON.parse(readFileSync(path, 'utf-8')) }
  catch { return [] }

  const routes = new Set<string>(['/ministries/', '/tags/'])
  for (const d of data.datasets ?? []) {
    if (d.organization_slug) routes.add(`/ministries/${d.organization_slug}/`)
    for (const t of d.tags_he ?? []) routes.add(`/tags/${encodeURIComponent(t)}/`)
    if (d.dataset_kind) routes.add(`/kinds/${d.dataset_kind}/`)
  }
  return [...routes]
}

export default defineNuxtConfig({
  ssr: true,
  compatibilityDate: '2025-01-01',
  devtools: { enabled: true },

  modules: ['@nuxtjs/tailwindcss'],

  components: [
    { path: '~/components', pathPrefix: false },
  ],

  app: {
    head: {
      htmlAttrs: { lang: 'he', dir: 'rtl' },
      title: 'GovData.IL',
      link: [
        { rel: 'preconnect', href: 'https://fonts.googleapis.com' },
        { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: '' },
        {
          rel: 'stylesheet',
          href: 'https://fonts.googleapis.com/css2?family=Rubik:wght@300;400;500;600;700&display=swap',
        },
      ],
      meta: [
        { charset: 'utf-8' },
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
        { name: 'theme-color', content: '#0068f5' },
        { name: 'generator', content: 'Nuxt + agentic AI pipeline' },
        { name: 'author', content: 'GovData.IL' },
        // Per-page useSeo() overrides these; they exist as fallbacks for
        // any page that forgets to call useSeo().
        { name: 'description', content: 'דפי נחיתה אוטומטיים בעברית למאגרי data.gov.il — נכתבים על ידי סוכן בינה מלאכותית (agentic AI).' },
        { name: 'keywords', content: 'מידע ממשלתי, data.gov.il, בינה מלאכותית, AI, סוכן AI, agentic, אג׳נטי, open data Israel' },
      ],
    },
  },

  nitro: {
    prerender: {
      crawlLinks: false,
      routes: [
        '/',
        '/datasets/',
        '/about/',
        '/how-it-works/',
        '/faq/',
        ...categoryRoutes(),
      ],
      failOnError: false,
    },
  },

  tailwindcss: {
    exposeConfig: false,
    viewer: false,
  },
})
