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

import { copyFileSync, existsSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createLogger } from 'vite'

const __dirname = dirname(fileURLToPath(import.meta.url))

interface ManifestEntry {
  id: string
  organization_slug?: string
  tags_he?: string[]
  suggested_tags?: string[]
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
    // Use the publisher-built tag_slugs map (Hebrew tag → URL-safe
    // Hebrew slug, with whitespace normalized to `-`). Pass the slug
    // raw — Nitro's prerender expects decoded routes and writes
    // Unicode-named directories from them. Union both CKAN-official
    // tags and the agent's suggested_tags so every chip on every
    // dataset page resolves to a generated tag page.
    for (const t of [...(d.tags_he ?? []), ...(d.suggested_tags ?? [])]) {
      const slug = tagSlugs[t]
      if (slug) routes.add(`/tags/${slug}/`)
    }
    if (d.dataset_kind) routes.add(`/kinds/${d.dataset_kind}/`)
  }
  return [...routes]
}

// Reads from manifest.json (the publisher's view of succeeded sources)
// rather than the filesystem. The rsync from staging can leave orphan
// content.html directories for sources whose Firestore status is now
// `pending` or `failed` — the publisher skips those, no data.json gets
// written, and prerendering them would 404 in [id].vue's fs.readFile.
function datasetRoutes(): string[] {
  const path = resolve(__dirname, 'public/data/manifest.json')
  try {
    const data = JSON.parse(readFileSync(path, 'utf-8')) as Manifest
    return (data.datasets ?? []).map((d) => `/datasets/${d.id}/`)
  } catch {
    return []
  }
}

export default defineNuxtConfig({
  ssr: true,
  compatibilityDate: '2025-01-01',
  devtools: { enabled: false },

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
        { rel: 'apple-touch-icon', href: '/apple-touch-icon.png' },
        { rel: 'manifest', href: '/site.webmanifest' },
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

  // Hebrew tag routes (e.g. /tags/אבטחה/) trigger a Nuxt 3.21 bug where
  // the prerender renderer puts the raw decoded URL into an
  // `x-nitro-prerender` HTTP header to hint Nitro to also prerender
  // /<route>/_payload.json — but HTTP header values must be Latin-1, so
  // any non-ASCII character throws `Cannot convert argument to a
  // ByteString`, returning a 500 for the whole route. Disabling payload
  // extraction skips that header entirely. Trade-off: client-side
  // navigation between prerendered pages refetches the HTML instead of
  // just a JSON payload, which is fine for this site (no SPA flow that
  // benefits from _payload.json).
  experimental: {
    payloadExtraction: false,
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
        '/accessibility/',
        ...categoryRoutes(),
        ...datasetRoutes(),
      ],
      failOnError: false,
    },
    // DrvFs polling for the Nitro server-route watcher — see comment on
    // `vite.server.watch` below for the broader story.
    watchOptions: { usePolling: true, interval: 300 },
  },

  tailwindcss: {
    exposeConfig: false,
    viewer: false,
  },

  // Repo lives on /mnt/d (WSL DrvFs) — inotify is unreliable across the
  // Windows↔Linux boundary, so default file watchers miss saves. Nuxt
  // runs three independent watchers in dev; all three need polling, or
  // HMR is silently partial (Vite-only polling reloads existing component
  // edits but misses new files / layout / config / server-route changes).
  //   1. Nuxt's chokidar — pages/, components/, layouts/, composables/,
  //      auto-imports, nuxt.config.ts (full restart)
  //   2. Nitro's watchOptions (above) — server/ routes
  //   3. Vite's server.watch — Vue SFC / CSS / JS HMR
  watchers: {
    chokidar: { usePolling: true, interval: 300 },
  },
  vite: {
    server: {
      watch: { usePolling: true, interval: 300 },
    },
    // Vite's default 500kB threshold is below the natural size of a
    // Nuxt 3.21 + Vue + Tailwind + components bundle for this app.
    // Echarts/Leaflet are NOT in this bundle (they load via useHead
    // from /lib/), so further code-splitting wouldn't move the needle.
    build: {
      chunkSizeWarningLimit: 1500,
    },
  },

  hooks: {
    // Suppress two cosmetic Vite warnings about node:fs/promises and node:path
    // being externalized for the browser. They come from pages/datasets/[id].vue's
    // useAsyncData fetcher, which is guarded by `if (!import.meta.server)` and
    // only ever runs during prerender. Vite emits the warning at resolve time
    // (before constant folding), so a runtime guard alone can't silence it.
    // We swap in a wrapped logger via the vite:extendConfig hook so this
    // overrides Nuxt's own logger setup.
    'vite:extendConfig' (viteConfig) {
      const logger = createLogger()
      const _warn = logger.warn.bind(logger)
      logger.warn = (msg, opts) => {
        if (
          typeof msg === 'string' &&
          /Module "node:(fs\/promises|path)" has been externalized/.test(msg)
        ) return
        _warn(msg, opts)
      }
      viteConfig.customLogger = logger
    },
  },
})
