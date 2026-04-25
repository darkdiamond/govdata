<script setup lang="ts">
import { useManifest } from '~/composables/useManifest'
import { formatBytes, formatNumber } from '~/composables/useRelativeTime'
import type { ManifestEntry } from '~/types/manifest'

const route = useRoute()
const id = String(route.params.id)

const { data } = await useAsyncData(`dataset-${id}`, async () => {
  const fs = await import('node:fs/promises')
  const path = await import('node:path')
  const dir = path.resolve(process.cwd(), 'public/datasets', id)

  const rawBody = await fs.readFile(path.join(dir, 'content.html'), 'utf-8')
  const body = rawBody.replace(/https:\/\/e\.data\.gov\.il/g, 'https://data.gov.il')

  const entry = JSON.parse(
    await fs.readFile(path.join(dir, 'data.json'), 'utf-8'),
  ) as ManifestEntry

  return { entry, body }
})

if (!data.value) {
  throw createError({ statusCode: 404, statusMessage: 'Dataset not found', fatal: true })
}

const entry = computed(() => data.value!.entry)
const body = computed(() => data.value!.body)

const manifest = useManifest()
const related = computed<ManifestEntry[]>(() => {
  const ids = entry.value.related_ids ?? []
  const byId = new Map((manifest.value?.datasets ?? []).map((d) => [d.id, d]))
  return ids
    .map((rid) => byId.get(rid))
    .filter((d): d is ManifestEntry => Boolean(d))
    .slice(0, 5)
})

const KIND_LABELS_HE: Record<string, string> = {
  map: 'גיאוגרפי',
  timeseries: 'סדרת זמן',
  registry: 'רשימת ישויות',
  rankings: 'דירוגים',
  misc: 'אחר',
}
const kindLabel = computed(() =>
  entry.value.dataset_kind ? KIND_LABELS_HE[entry.value.dataset_kind] ?? 'אחר' : '',
)

const hasMeta = computed(() =>
  Boolean(
    entry.value.organization ||
      entry.value.license ||
      entry.value.metadata_modified ||
      entry.value.record_count != null,
  ),
)

const HE_DATE = new Intl.DateTimeFormat('he-IL', { dateStyle: 'long' })
function formatDateHe(iso?: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '' : HE_DATE.format(d)
}
function publicResourceUrl(url: string): string {
  return url.replace('https://e.data.gov.il', 'https://data.gov.il')
}
function formatClass(fmt?: string | null): string {
  switch ((fmt || '').toUpperCase()) {
    case 'CSV':  return 'fmt-csv'
    case 'PDF':  return 'fmt-pdf'
    case 'XLSX':
    case 'XLS':  return 'fmt-xlsx'
    case 'JSON': return 'fmt-json'
    default:     return 'fmt-default'
  }
}

useSeo({
  title: entry.value.title,
  description: (entry.value.summary_he ?? entry.value.title).slice(0, 160),
  path: `/datasets/${entry.value.id}/`,
})

// Agent-generated content.html has inline <script> tags (ECharts, Leaflet).
// On SSR/refresh they execute natively as the browser parses the document,
// but v-html sets innerHTML, and innerHTML-inserted scripts never run — so
// on client-side navigation the charts silently fail to initialize. Rebuild
// each <script> as a real element so the browser executes it, awaiting
// external src= loads so inline init scripts see their globals. Inline
// classic scripts get wrapped in an IIFE because top-level `const`/`let`
// bind into the page's shared script-level scope, which persists across
// SPA navs and would SyntaxError on re-entry to a previously-visited page.
const bodyEl = ref<HTMLElement | null>(null)
const nuxtApp = useNuxtApp()

async function executeBodyScripts(container: HTMLElement): Promise<void> {
  const scripts = Array.from(container.querySelectorAll('script'))
  // content.html often gates init on DOMContentLoaded / window load, but those
  // events fired once on the original page load and never fire again. Intercept
  // addEventListener while our scripts run, collect handlers registered for
  // those events, and invoke them immediately after — without touching
  // listeners registered earlier (which would double-init prior visits).
  type Deferred = [EventTarget, string, EventListenerOrEventListenerObject]
  const deferred: Deferred[] = []
  const origDocAdd = document.addEventListener
  const origWinAdd = window.addEventListener
  const docReady = () => document.readyState !== 'loading'
  const winLoaded = () => document.readyState === 'complete'
  document.addEventListener = function (type: string, listener: EventListenerOrEventListenerObject, opts?: unknown) {
    if (listener && (type === 'DOMContentLoaded' || type === 'readystatechange') && docReady()) {
      deferred.push([document, type, listener])
      return
    }
    return origDocAdd.call(document, type as keyof DocumentEventMap, listener as EventListener, opts as AddEventListenerOptions)
  } as typeof document.addEventListener
  window.addEventListener = function (type: string, listener: EventListenerOrEventListenerObject, opts?: unknown) {
    if (listener && type === 'load' && winLoaded()) {
      deferred.push([window, type, listener])
      return
    }
    return origWinAdd.call(window, type as keyof WindowEventMap, listener as EventListener, opts as AddEventListenerOptions)
  } as typeof window.addEventListener
  try {
    for (const old of scripts) {
      const parent = old.parentNode
      if (!parent) continue
      const s = document.createElement('script')
      for (const { name, value } of Array.from(old.attributes)) s.setAttribute(name, value)
      if (s.src) {
        await new Promise<void>((resolve) => {
          s.onload = () => resolve()
          s.onerror = () => resolve()
          parent.replaceChild(s, old)
        })
      } else {
        const source = old.textContent ?? ''
        s.text = s.type === 'module' ? source : `(()=>{\n${source}\n})();`
        parent.replaceChild(s, old)
      }
    }
  } finally {
    document.addEventListener = origDocAdd
    window.addEventListener = origWinAdd
  }
  for (const [target, type, listener] of deferred) {
    try {
      const ev = new Event(type)
      if (typeof listener === 'function') listener.call(target, ev)
      else listener.handleEvent(ev)
    } catch (err) {
      console.error('[dataset body] deferred listener failed', err)
    }
  }
}

onMounted(() => {
  if (nuxtApp.isHydrating) return
  if (bodyEl.value) void executeBodyScripts(bodyEl.value)
})
</script>

<template>
  <div>
    <nav aria-label="breadcrumb" class="border-b border-rule bg-white">
      <div class="max-w-gov mx-auto px-4 py-2 text-xs text-subtle">
        <NuxtLink to="/">ראשי</NuxtLink>
        <template v-if="entry.organization && entry.organization_slug">
          <span class="mx-1">›</span>
          <NuxtLink :to="`/ministries/${entry.organization_slug}/`">{{ entry.organization }}</NuxtLink>
        </template>
        <span class="mx-1">›</span>
        <span>{{ entry.title }}</span>
      </div>
    </nav>

    <div
      v-if="hasMeta || entry.resources?.length"
      class="max-w-gov mx-auto px-4 pt-6"
    >
      <div class="grid md:grid-cols-2 gap-4">
        <section v-if="hasMeta" class="card p-5">
          <h3 class="m-0 mb-3 text-sm font-display text-subtle">פרטים</h3>
          <dl class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm m-0">
            <template v-if="entry.organization">
              <dt class="text-subtle">משרד</dt>
              <dd class="m-0">
                <NuxtLink
                  v-if="entry.organization_slug"
                  :to="`/ministries/${entry.organization_slug}/`"
                >{{ entry.organization }}</NuxtLink>
                <template v-else>{{ entry.organization }}</template>
              </dd>
            </template>
            <template v-if="entry.license">
              <dt class="text-subtle">רישיון</dt>
              <dd class="m-0">{{ entry.license }}</dd>
            </template>
            <template v-if="entry.metadata_modified">
              <dt class="text-subtle">עודכן</dt>
              <dd class="m-0">{{ formatDateHe(entry.metadata_modified) }}</dd>
            </template>
            <template v-if="entry.record_count != null">
              <dt class="text-subtle">רשומות</dt>
              <dd class="m-0">{{ formatNumber(entry.record_count) }}</dd>
            </template>
          </dl>
        </section>

        <section v-if="entry.resources?.length" class="card p-5">
          <h3 class="m-0 mb-3 text-sm font-display text-subtle">קבצים להורדה</h3>
          <div>
            <div v-for="r in entry.resources" :key="r.url" class="res-row">
              <span :class="['fmt-badge', formatClass(r.format)]">{{ (r.format || 'FILE').toUpperCase() }}</span>
              <div class="flex-1 min-w-0">
                <div class="text-sm text-ink truncate">{{ r.name || r.format || 'קובץ' }}</div>
                <div v-if="r.size_bytes" class="text-xs text-subtle">{{ formatBytes(r.size_bytes) }}</div>
              </div>
              <a
                :href="publicResourceUrl(r.url)"
                class="btn-ghost text-xs px-3 py-1.5"
                target="_blank"
                rel="noopener"
                download
              >הורדה</a>
            </div>
          </div>
        </section>
      </div>
    </div>

    <div class="max-w-gov mx-auto px-4 py-8 grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-8">
      <article ref="bodyEl" class="dataset-body" v-html="body" />

      <aside class="space-y-4">
        <section v-if="related.length" class="card p-4">
          <h3 class="m-0 mb-3 text-sm text-subtle font-display">מאגרים קשורים</h3>
          <ul class="list-none m-0 p-0 space-y-2">
            <li v-for="r in related" :key="r.id">
              <NuxtLink
                :to="`/datasets/${r.id}/`"
                class="block card-hover p-2 rounded-gov-md hover:bg-brand-50 no-underline hover:no-underline"
              >
                <div class="text-sm font-medium text-ink">{{ r.title }}</div>
                <div v-if="r.organization" class="text-xs text-subtle mt-0.5">{{ r.organization }}</div>
                <div v-if="r.summary_he" class="text-xs text-subtle mt-1 line-clamp-2">{{ r.summary_he }}</div>
              </NuxtLink>
            </li>
          </ul>
        </section>

        <section v-if="entry.tags_he?.length" class="card p-4">
          <h3 class="m-0 mb-2 text-sm text-subtle font-display">תגיות</h3>
          <div class="flex flex-wrap gap-1">
            <NuxtLink
              v-for="t in entry.tags_he"
              :key="t"
              :to="`/tags/${encodeURIComponent(t)}/`"
              class="tag-chip hover:bg-brand-100"
            >{{ t }}</NuxtLink>
          </div>
        </section>

        <section v-if="entry.dataset_kind" class="card p-4 text-xs text-subtle">
          סוג מאגר:
          <NuxtLink :to="`/kinds/${entry.dataset_kind}/`" class="badge hover:bg-brand-50">{{ kindLabel }}</NuxtLink>
        </section>
      </aside>
    </div>
  </div>
</template>
