<script setup lang="ts">
import { useFacets, useManifest } from '~/composables/useManifest'
import type { ManifestEntry } from '~/types/manifest'

useSeo({
  title: 'כל מאגרי המידע הממשלתיים — חיפוש, סינון ותקצירי AI',
  description: 'סיור, חיפוש וסינון של כל מאגרי המידע הציבוריים של ממשלת ישראל — לפי משרד, פורמט ותגיות.',
  path: '/datasets/',
  breadcrumbs: [
    { name: 'ראשי', url: 'https://govil.ai/' },
    { name: 'מאגרים', url: 'https://govil.ai/datasets/' },
  ],
})

const manifest = useManifest()
const datasets = computed<ManifestEntry[]>(() => manifest.value?.datasets ?? [])
const { organizations, formats } = useFacets(datasets.value)

const route = useRoute()
const router = useRouter()

type SortKey = 'gov' | 'site' | 'alpha'
const SORT_KEYS = ['gov', 'site', 'alpha'] as const
const isSortKey = (v: unknown): v is SortKey =>
  typeof v === 'string' && (SORT_KEYS as readonly string[]).includes(v)

const orgFilter = ref<string | null>(null)
const formatFilter = ref<string | null>(null)
const initialQ = typeof route.query.q === 'string' ? route.query.q : ''
const query = ref(initialQ)
const debouncedQuery = ref(initialQ)
const sortKey = ref<SortKey>(isSortKey(route.query.sort) ? route.query.sort : 'gov')

let debounceTimer: ReturnType<typeof setTimeout> | null = null
watch(query, (q) => {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    debouncedQuery.value = q
  }, 150)
})
onBeforeUnmount(() => {
  if (debounceTimer) clearTimeout(debounceTimer)
})

watch(debouncedQuery, (q) => {
  const next = q.trim() ? { ...route.query, q: q.trim() } : { ...route.query, q: undefined }
  router.replace({ query: next })
})

const filtered = computed<ManifestEntry[]>(() => {
  const q = debouncedQuery.value.trim().toLowerCase()
  return datasets.value.filter((d) => {
    if (orgFilter.value && d.organization !== orgFilter.value) return false
    if (formatFilter.value && !d.formats.includes(formatFilter.value)) return false
    if (q) {
      const hay = `${d.title} ${d.summary_he ?? ''} ${d.tags_he.join(' ')}`.toLowerCase()
      if (!hay.includes(q)) return false
    }
    return true
  })
})

const tsDesc = (a?: string, b?: string) =>
  (b ? Date.parse(b) : 0) - (a ? Date.parse(a) : 0)

const sortedFiltered = computed<ManifestEntry[]>(() => {
  const list = [...filtered.value]
  if (sortKey.value === 'site') {
    list.sort((a, b) => tsDesc(a.last_analyzed_at, b.last_analyzed_at))
  } else if (sortKey.value === 'alpha') {
    list.sort((a, b) => a.title.localeCompare(b.title, 'he'))
  } else {
    list.sort((a, b) => tsDesc(a.metadata_modified, b.metadata_modified))
  }
  return list
})

function clear() {
  orgFilter.value = null
  formatFilter.value = null
  query.value = ''
  debouncedQuery.value = ''
}

watch(
  () => route.query.q,
  (q) => {
    const v = typeof q === 'string' ? q : ''
    if (v !== query.value) {
      query.value = v
      debouncedQuery.value = v
    }
  },
)

watch(sortKey, (s) => {
  const next = { ...route.query, sort: s === 'gov' ? undefined : s }
  router.replace({ query: next })
})

watch(
  () => route.query.sort,
  (s) => {
    const v = isSortKey(s) ? s : 'gov'
    if (v !== sortKey.value) sortKey.value = v
  },
)
</script>

<template>
  <div class="max-w-gov mx-auto px-4 py-8">
    <section class="mb-8">
      <div class="text-xs text-subtle mb-2">
        <NuxtLink to="/">ראשי</NuxtLink> › מאגרים
      </div>
      <h1 class="font-display">כל המאגרים</h1>
      <p class="text-subtle mt-2 max-w-2xl">
        {{ datasets.length }} מאגרים מאורגנים לפי משרד, פורמט ותגיות. לחץ על מאגר כדי לראות את דף ה-AI שנכתב עבורו.
      </p>
      <label class="mt-4 flex items-center gap-2 bg-white border border-rule rounded-gov px-3 py-2 max-w-xl focus-within:border-brand transition-colors">
        <img src="/icons/search.svg" alt="" class="w-5 h-5 opacity-70" />
        <input
          v-model="query"
          type="search"
          placeholder="חיפוש מאגר, נושא או משרד…"
          class="flex-1 bg-transparent border-0 outline-none text-sm text-ink placeholder:text-subtle"
        />
      </label>
    </section>

    <section class="grid grid-cols-1 lg:grid-cols-[1fr_260px] gap-8">
      <div>
        <div class="flex items-center justify-between gap-3 mb-3 text-sm">
          <span class="text-subtle">{{ filtered.length }} מאגרים זמינים</span>
          <div class="flex items-center gap-3">
            <button
              v-if="orgFilter || formatFilter || query"
              @click="clear"
              class="text-brand hover:underline"
            >
              איפוס פילטרים
            </button>
            <label class="flex items-center gap-2">
              <span class="text-subtle">מיון:</span>
              <select
                v-model="sortKey"
                class="bg-white border border-rule rounded-gov px-2 py-1 text-ink focus:border-brand outline-none"
              >
                <option value="gov">חדש בממשלה</option>
                <option value="site">חדש באתר</option>
                <option value="alpha">א–ת</option>
              </select>
            </label>
          </div>
        </div>

        <div v-if="datasets.length === 0" class="card p-6 text-center text-subtle">
          <p class="m-0">עדיין לא נוצרו דפים. הפעל את הסורק + ה-page-builder כדי להתחיל.</p>
        </div>

        <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-3">
          <DatasetCard v-for="d in sortedFiltered" :key="d.id" :entry="d" />
        </div>
      </div>

      <aside class="space-y-4">
        <div class="card p-4">
          <h3 class="m-0 mb-2 text-sm text-subtle font-display">ארגון</h3>
          <ul class="list-none m-0 p-0 space-y-1">
            <li v-for="[org, n] in organizations" :key="org">
              <button
                class="w-full text-right text-sm px-2 py-1 rounded-md hover:bg-surface flex items-center justify-between gap-2"
                :class="{ 'bg-brand-50 text-brand-700': orgFilter === org }"
                @click="orgFilter = orgFilter === org ? null : org"
              >
                <span class="truncate">{{ org }}</span>
                <span class="text-xs text-subtle">{{ n }}</span>
              </button>
            </li>
          </ul>
        </div>
        <div class="card p-4">
          <h3 class="m-0 mb-2 text-sm text-subtle font-display">פורמט</h3>
          <div class="flex flex-wrap gap-1">
            <button
              v-for="[fmt, n] in formats"
              :key="fmt"
              class="badge hover:bg-brand-50"
              :class="{ '!bg-brand-50 !text-brand-700 !border-brand-100': formatFilter === fmt }"
              @click="formatFilter = formatFilter === fmt ? null : fmt"
            >
              {{ fmt }} · {{ n }}
            </button>
          </div>
        </div>
      </aside>
    </section>
  </div>
</template>
