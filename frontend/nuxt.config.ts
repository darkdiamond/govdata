// Nuxt generates every page on the site, including dataset landing pages.
// For each dataset under public/datasets/<id>/, pages/datasets/[id].vue
// reads three artifacts at build time and renders them inside the default
// layout — so header/footer live in one place (layouts/default.vue) and
// can never drift from dataset pages:
//   content.html      — agent body, synced from GCS
//   data.json         — DatasetMeta (scanner facts), written by the publisher
//   agent_data.json   — AgentData (agent judgments), written by the publisher
// Category routes (ministries/tags/kinds) are enumerated from manifest.json
// (the merged view) the same way.

import { copyFileSync, existsSync, readdirSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))

interface ManifestEntry {
  id: string
  organization_slug?: string
  tags_he?: string[]
  dataset_kind?: string
}
interface Manifest {
  datasets?: ManifestEntry[]
  tag_slugs?: Record<string, string>
}

function categoryRoutes(): string[] {
  const path = resolve(__dirname, 'public/data/manifest.json')
  let data: Manifest
  try { data = JSON.parse(readFileSync(path, 'utf-8')) }
  catch { return [] }

  const tagSlugs = data.tag_slugs ?? {}
  const routes = new Set<string>(['/ministries/', '/tags/'])
  for (const d of data.datasets ?? []) {
    if (d.organization_slug) routes.add(`/ministries/${d.organization_slug}/`)
    // Use the publisher-built Hebrew→Latin map. Falls back to a defensive
    // skip for any tag that's somehow missing from the map (shouldn't
    // happen — publisher unions every tags_he), avoiding a non-ASCII
    // directory creation that would break prerender on Windows/WSL.
    for (const t of d.tags_he ?? []) {
      const slug = tagSlugs[t]
      if (slug) routes.add(`/tags/${slug}/`)
    }
    if (d.dataset_kind) routes.add(`/kinds/${d.dataset_kind}/`)
  }
  return [...routes]
}

function datasetRoutes(): string[] {
  const dir = resolve(__dirname, 'public/datasets')
  try {
    return readdirSync(dir, { withFileTypes: true })
      .filter((d) => d.isDirectory())
      .map((d) => `/datasets/${d.name}/`)
  } catch {
    return []
  }
}

export default defineNuxtConfig({
  ssr: true,
  compatibilityDate: '2025-01-01',
  devtools: { enabled: true },

  // The generated `.nuxt/tsconfig.json` sets `types: []` and includes
  // `webworker` in `lib`. Build-time helpers in this file (and prerender
  // hooks like `categoryRoutes`) need Node globals, so inject `node`.
  typescript: {
    tsConfig: {
      compilerOptions: {
        types: ['node'],
      },
    },
  },

  modules: ['@nuxtjs/tailwindcss', 'nuxt-gtag'],

  gtag: {
    id: 'G-1P3DPS2M2Q',
  },

  components: [
    { path: '~/components', pathPrefix: false },
  ],

  app: {
    head: {
      htmlAttrs: { lang: 'he', dir: 'rtl' },
      title: 'govil.ai',
      link: [
        { rel: 'icon', type: 'image/svg+xml', href: '/favicon.svg' },
        { rel: 'icon', href: '/favicon.ico', sizes: 'any' },
        { rel: 'icon', type: 'image/png', sizes: '192x192', href: '/favicon-192.png' },
        { rel: 'apple-touch-icon', href: '/apple-touch-icon.png' },
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
        { name: 'author', content: 'govil.ai' },
        // Per-page useSeo() overrides these; they exist as fallbacks for
        // any page that forgets to call useSeo().
        { name: 'description', content: 'דפי נחיתה אוטומטיים למאגרי data.gov.il — נכתבים על ידי סוכן בינה מלאכותית (agentic AI).' },
        { name: 'keywords', content: 'מידע ממשלתי, data.gov.il, בינה מלאכותית, AI, סוכן AI, agentic, אג׳נטי, open data Israel' },
        { name: 'google-adsense-account', content: 'ca-pub-9066544714340882' },
      ],
      script: [
        {
          async: true,
          src: 'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-9066544714340882',
          crossorigin: 'anonymous',
        },
      ],
    },
  },

  nitro: {
    // Nitro writes an empty SPA-fallback `404.html` by design (confirmed
    // by Nuxt maintainer in nuxt/nuxt#21937). To get a server-rendered
    // 404 page on Firebase Hosting (which serves `404.html` at the root
    // for unmatched routes), we prerender `/404/` as a real page and
    // mirror that file over the empty fallback once Nitro finishes.
    hooks: {
      'compiled' (nitro) {
        const out = nitro.options.output.publicDir
        const src = resolve(out, '404/index.html')
        const dst = resolve(out, '404.html')
        if (existsSync(src)) copyFileSync(src, dst)
      },
    },
    prerender: {
      crawlLinks: false,
      routes: [
        '/',
        '/404/',
        '/datasets/',
        '/about/',
        '/how-it-works/',
        '/faq/',
        '/contact/',
        '/privacy/',
        '/terms/',
        ...categoryRoutes(),
        ...datasetRoutes(),
      ],
      failOnError: false,
    },
  },

  tailwindcss: {
    exposeConfig: false,
    viewer: false,
  },

  // Repo lives on /mnt/d (WSL DrvFs) — inotify is unreliable across the
  // Windows↔Linux boundary, so Vite's default watcher misses saves. Use
  // chokidar polling so HMR fires reliably in dev.
  vite: {
    server: {
      watch: {
        usePolling: true,
        interval: 300,
      },
    },
  },
})
