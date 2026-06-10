<script setup lang="ts">
// Shell-owned data explorer: search + paginated table over the CKAN
// datastore_search API, built per dataset from data.json's resources.
// Replaces the agent-built GovExplorer sections (stripped by
// normalizeAgentBody) — unlike those, search here is SERVER-SIDE via the
// `q` parameter, so it covers every record in the resource, not just the
// rows already loaded. CORS: data.gov.il allows plain GETs to
// /api/3/action/ with no custom headers, so no preflight is issued.
import type { ResourceEntry } from '~/types/manifest'

const props = defineProps<{
  resources: ResourceEntry[]
  primaryResourceId?: string
  recordCount?: number
}>()

const API = 'https://data.gov.il/api/3/action/datastore_search'
const PAGE_SIZE = 50
// Show every column — many CKAN resources keep their meaningful identity
// columns (names, dates, statuses) at the END of the field list, so any
// small cap hides exactly the wrong half. The wrapper scrolls
// horizontally. MAX_COLS is only a backstop against pathological
// resources (hundreds of columns) where a table stops making sense.
const MAX_COLS = 60

interface Candidate {
  rid: string
  name: string
  format: string
  url: string
  /** Legacy data.json has no datastore_active flags — the runtime
   *  limit=0 probe decides whether the section stays. */
  verified: boolean
}

interface Col {
  id: string
  numeric: boolean
  date: boolean
}

interface DsResult {
  records: Record<string, unknown>[]
  total: number
  fields?: { id: string; type: string }[]
}

const RESOURCE_URL_RE = /\/resource\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\//

function resourceId(r: ResourceEntry): string | null {
  return r.id ?? r.url.match(RESOURCE_URL_RE)?.[1] ?? null
}

const candidates = computed<Candidate[]>(() => {
  const resources = props.resources ?? []
  const hasFlags = resources.some((r) => typeof r.datastore_active === 'boolean')
  const out: Candidate[] = []
  const seen = new Set<string>()

  if (hasFlags) {
    for (const r of resources) {
      const rid = resourceId(r)
      if (!rid || seen.has(rid) || r.datastore_active !== true) continue
      seen.add(rid)
      out.push({ rid, name: r.name || r.format || 'קובץ', format: (r.format || '').toUpperCase(), url: r.url, verified: true })
    }
    // Primary resource first — it's the file the page's content is based on.
    out.sort((a, b) => Number(b.rid === props.primaryResourceId) - Number(a.rid === props.primaryResourceId))
    return out
  }

  // Legacy data.json (no flags anywhere): expose only the primary resource,
  // unverified — the schema probe collapses the section if it isn't
  // datastore-backed. Probing every resource per page view would be too
  // chatty for a question whose answer is static.
  const primary =
    resources.find((r) => resourceId(r) === props.primaryResourceId) ??
    resources.find((r) => resourceId(r) !== null)
  const rid = primary ? resourceId(primary) : null
  if (primary && rid) {
    out.push({ rid, name: primary.name || primary.format || 'קובץ', format: (primary.format || '').toUpperCase(), url: primary.url, verified: false })
  }
  return out
})

const droppedRids = ref<Set<string>>(new Set())
const visibleCandidates = computed(() => candidates.value.filter((c) => !droppedRids.value.has(c.rid)))

const collapsed = ref(false)
const activeRid = ref<string | null>(null)
const rows = ref<Record<string, unknown>[]>([])
const total = ref(0)
const offset = ref(0)
const searchText = ref('')
const query = ref('')
const loading = ref(false)
const fetchError = ref(false)
// Server-side sort over the whole resource, like search. null = CKAN's
// default order (_id, or rank under q).
const sortCol = ref<string | null>(null)
const sortDir = ref<'asc' | 'desc'>('asc')

interface Schema {
  cols: Col[]
  totalCols: number
  baseTotal: number
}
const schemaCache = new Map<string, Schema>()
const schema = ref<Schema | null>(null)

let reqSeq = 0
let aborter: AbortController | null = null

const NUMERIC_TYPES = new Set(['int', 'int4', 'int8', 'float', 'float4', 'float8', 'numeric', 'double precision', 'bigint', 'integer'])
const DATE_TYPES = new Set(['date', 'timestamp', 'timestamptz', 'time'])
const HIDDEN_FIELDS = new Set(['_id', '_full_text', 'rank'])

async function dsSearch(
  p: { resource_id: string; limit: number; offset?: number; q?: string; sort?: string },
  signal?: AbortSignal,
): Promise<DsResult> {
  const params = new URLSearchParams({
    resource_id: p.resource_id,
    limit: String(p.limit),
    include_total: 'true',
  })
  if (p.offset) params.set('offset', String(p.offset))
  if (p.q) params.set('q', p.q)
  if (p.sort) params.set('sort', p.sort)
  const res = await fetch(`${API}?${params}`, { signal })
  if (!res.ok) throw new Error(`http ${res.status}`)
  const data = await res.json()
  if (!data?.success || !data.result) throw new Error('ckan reject')
  return {
    records: data.result.records ?? [],
    total: data.result.total ?? 0,
    fields: data.result.fields,
  }
}

// Returns the schema (possibly with zero usable columns — a valid but
// empty datastore, e.g. a resource that was registered and never
// loaded); null only when the probe itself fails (not datastore-backed,
// 404, network). The distinction matters: probe failure drops the
// tab/section, an empty datastore keeps its tab with an empty state.
async function loadSchema(rid: string): Promise<Schema | null> {
  const cached = schemaCache.get(rid)
  if (cached) return cached
  try {
    const res = await dsSearch({ resource_id: rid, limit: 0 })
    const all = (res.fields ?? []).filter((f) => !HIDDEN_FIELDS.has(f.id))
    const sch: Schema = {
      cols: all.slice(0, MAX_COLS).map((f) => {
        const t = (f.type || '').toLowerCase()
        return { id: f.id, numeric: NUMERIC_TYPES.has(t), date: DATE_TYPES.has(t) }
      }),
      totalCols: all.length,
      baseTotal: res.total,
    }
    schemaCache.set(rid, sch)
    return sch
  } catch {
    return null
  }
}

async function activate(rid: string) {
  const cand = visibleCandidates.value.find((c) => c.rid === rid)
  if (!cand) return
  activeRid.value = rid
  loading.value = true
  fetchError.value = false
  const sch = await loadSchema(rid)
  if (activeRid.value !== rid) return // user switched away mid-probe
  if (!sch) {
    // Resource isn't datastore-backed (or the datastore was dropped since
    // the scan). Unverified single candidate → the whole section goes;
    // verified candidate with siblings → drop just this tab.
    droppedRids.value = new Set([...droppedRids.value, rid])
    const next = visibleCandidates.value[0]
    if (next) void activate(next.rid)
    else collapsed.value = true
    return
  }
  schema.value = sch
  offset.value = 0
  sortCol.value = null
  sortDir.value = 'asc'
  if (!sch.cols.length) {
    // Valid datastore with no usable columns (empty resource) — keep the
    // tab, render the empty state instead of dropping the button the
    // user just clicked.
    rows.value = []
    total.value = 0
    loading.value = false
    return
  }
  await loadPage()
}

async function loadPage() {
  const rid = activeRid.value
  const sch = schema.value
  if (!rid || !sch) return
  const seq = ++reqSeq
  aborter?.abort()
  aborter = new AbortController()
  loading.value = true
  fetchError.value = false
  try {
    const res = await dsSearch(
      {
        resource_id: rid,
        limit: PAGE_SIZE,
        offset: offset.value,
        q: query.value || undefined,
        // Quoted form handles field ids with spaces or commas (verified
        // against data.gov.il). Ids containing `"` are unsortable.
        sort: sortCol.value ? `"${sortCol.value}" ${sortDir.value}` : undefined,
      },
      aborter.signal,
    )
    if (seq !== reqSeq) return
    rows.value = res.records
    total.value = res.total
    loading.value = false
  } catch (err) {
    if (seq !== reqSeq || (err instanceof DOMException && err.name === 'AbortError')) return
    rows.value = []
    total.value = 0
    fetchError.value = true
    loading.value = false
  }
}

let debounceTimer: ReturnType<typeof setTimeout> | undefined
function onSearchInput() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    const q = searchText.value.trim()
    if (q === query.value) return
    query.value = q
    offset.value = 0
    void loadPage()
  }, 350)
}

function nextPage() {
  if (offset.value + PAGE_SIZE >= total.value) return
  offset.value += PAGE_SIZE
  void loadPage()
}
function prevPage() {
  if (offset.value === 0) return
  offset.value = Math.max(0, offset.value - PAGE_SIZE)
  void loadPage()
}

function sortable(colId: string): boolean {
  return !colId.includes('"')
}

function toggleSort(colId: string) {
  if (!sortable(colId)) return
  if (sortCol.value === colId) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortCol.value = colId
    sortDir.value = 'asc'
  }
  offset.value = 0
  void loadPage()
}

function ariaSort(colId: string): 'ascending' | 'descending' | 'none' {
  if (sortCol.value !== colId) return 'none'
  return sortDir.value === 'asc' ? 'ascending' : 'descending'
}

function switchResource(rid: string) {
  if (rid === activeRid.value) return
  offset.value = 0
  void activate(rid)
}

const HE_NUM = (n: number) => n.toLocaleString('he-IL')

// Valid datastore with no usable columns — the resource is registered
// but holds no data. Renders an empty state instead of search + table.
const schemaEmpty = computed(() => Boolean(schema.value && !schema.value.cols.length))

const rangeText = computed(() => {
  if (!total.value) return ''
  const from = offset.value + 1
  const to = Math.min(offset.value + rows.value.length, total.value)
  const base = `מציג ${HE_NUM(from)}–${HE_NUM(to)} מתוך ${HE_NUM(total.value)} רשומות`
  if (query.value && schema.value) {
    return `נמצאו ${HE_NUM(total.value)} רשומות תואמות מתוך ${HE_NUM(schema.value.baseTotal)} — ${base}`
  }
  return base
})

// Many CKAN columns store dates as text — "2027-04-06 00:00:00.000".
// Trim the redundant midnight time for display; non-midnight times are
// meaningful and kept verbatim.
const MIDNIGHT_RE = /^(\d{4}-\d{2}-\d{2})[T ]00:00:00(?:\.0+)?$/

function cellText(v: unknown, col: Col): string {
  if (v === null || v === undefined || v === '') return '—'
  const s = String(v)
  if (col.date) return s.slice(0, 10)
  const m = s.match(MIDNIGHT_RE)
  if (m) return m[1]!
  return s
}

onMounted(() => {
  const first = visibleCandidates.value[0]
  if (first) void activate(first.rid)
})

onBeforeUnmount(() => {
  clearTimeout(debounceTimer)
  aborter?.abort()
})
</script>

<template>
  <section
    v-if="visibleCandidates.length && !collapsed"
    class="card p-5 mt-8"
    dir="rtl"
    aria-label="עיון בנתונים"
  >
    <div class="flex items-center gap-2 mb-3">
      <img src="/icons/database.svg" alt="" class="w-5 h-5" />
      <h2 class="m-0 text-lg font-semibold text-ink-deep">עיון בנתונים</h2>
    </div>

    <div v-if="visibleCandidates.length > 1" class="flex flex-wrap gap-2 mb-3" role="group" aria-label="בחירת קובץ">
      <button
        v-for="c in visibleCandidates"
        :key="c.rid"
        type="button"
        class="explorer-pill"
        :class="{ 'explorer-pill--active': c.rid === activeRid }"
        :aria-pressed="c.rid === activeRid"
        @click="switchResource(c.rid)"
      >
        <span class="max-w-[40ch] truncate">{{ c.name }}</span>
        <span v-if="c.format" class="explorer-pill-fmt">{{ c.format }}</span>
      </button>
    </div>

    <template v-if="!schemaEmpty">
      <input
        v-model="searchText"
        type="search"
        class="explorer-search"
        placeholder="חיפוש ברשומות…"
        aria-label="חיפוש בכל רשומות המאגר"
        @input="onSearchInput"
      />
      <p class="m-0 mt-1.5 mb-3 text-xs text-subtle">
        החיפוש מתבצע בכל הרשומות במאגר, לפי מילים שלמות
      </p>
    </template>

    <div v-if="schemaEmpty" class="explorer-state">
      אין רשומות זמינות לעיון בקובץ זה.
      <a :href="visibleCandidates.find((c) => c.rid === activeRid)?.url" target="_blank" rel="noopener">להורדת הקובץ</a>
    </div>

    <div v-else class="overflow-x-auto" :aria-busy="loading">
      <table v-if="schema" class="explorer-tbl" :class="{ 'opacity-50': loading && rows.length }">
        <caption class="sr-only">תוכן המאגר — תוצאות מעומדות בטבלה</caption>
        <thead>
          <tr>
            <th
              v-for="col in schema.cols"
              :key="col.id"
              scope="col"
              :aria-sort="sortable(col.id) ? ariaSort(col.id) : undefined"
            >
              <button
                v-if="sortable(col.id)"
                type="button"
                class="th-sort"
                :class="{ 'th-sort--active': sortCol === col.id }"
                @click="toggleSort(col.id)"
              >
                <span>{{ col.id }}</span>
                <span class="th-sort-arrow" aria-hidden="true">{{
                  sortCol === col.id ? (sortDir === 'asc' ? '▲' : '▼') : '↕'
                }}</span>
              </button>
              <template v-else>{{ col.id }}</template>
            </th>
          </tr>
        </thead>
        <tbody>
          <template v-if="loading && !rows.length">
            <tr v-for="i in 5" :key="`skel-${i}`">
              <td :colspan="schema.cols.length"><span class="explorer-skel" :style="{ width: `${100 - i * 8}%` }" /></td>
            </tr>
          </template>
          <tr v-else-if="fetchError">
            <td :colspan="schema.cols.length" class="explorer-state explorer-state--error">
              לא ניתן לטעון את הנתונים כעת.
              <a :href="visibleCandidates.find((c) => c.rid === activeRid)?.url" target="_blank" rel="noopener">להורדת הקובץ המלא</a>
            </td>
          </tr>
          <tr v-else-if="!rows.length">
            <td :colspan="schema.cols.length" class="explorer-state">לא נמצאו רשומות תואמות</td>
          </tr>
          <tr v-for="(row, ri) in rows" :key="`${offset}-${ri}`">
            <td
              v-for="col in schema.cols"
              :key="col.id"
              :dir="col.numeric || col.date ? 'ltr' : 'auto'"
              :class="{ 'text-end tabular-nums': col.numeric || col.date }"
              :title="cellText(row[col.id], col).length > 60 ? cellText(row[col.id], col) : undefined"
            >{{ cellText(row[col.id], col) }}</td>
          </tr>
        </tbody>
      </table>
      <div v-else-if="loading" class="py-6">
        <span v-for="i in 3" :key="i" class="explorer-skel" :style="{ width: `${100 - i * 12}%` }" />
      </div>
    </div>

    <p v-if="schema && schema.totalCols > schema.cols.length" class="m-0 mt-2 text-xs text-subtle">
      מוצגות {{ schema.cols.length }} מתוך {{ schema.totalCols }} עמודות —
      <a :href="visibleCandidates.find((c) => c.rid === activeRid)?.url" target="_blank" rel="noopener">לצפייה בכל העמודות הורידו את הקובץ</a>
    </p>

    <div v-if="total > PAGE_SIZE || offset > 0 || rangeText" class="flex flex-wrap items-center gap-3 mt-3">
      <template v-if="total > PAGE_SIZE">
        <button type="button" class="btn-ghost text-xs px-3 py-1.5" :disabled="offset === 0 || loading" @click="prevPage">הקודם</button>
        <button type="button" class="btn-ghost text-xs px-3 py-1.5" :disabled="offset + PAGE_SIZE >= total || loading" @click="nextPage">הבא</button>
      </template>
      <span class="text-xs text-subtle">{{ rangeText }}</span>
    </div>
  </section>
</template>

<style scoped>
.explorer-search {
  width: 100%;
  max-width: 420px;
  border: 1px solid #c3cfe7;
  border-radius: 0.3rem;
  padding: 0.4rem 0.75rem;
  font-family: Rubik, sans-serif;
  font-size: 0.9rem;
  color: #0c3058;
  background: #fff;
}
.explorer-search:focus {
  outline: 2px solid #0068f5;
  outline-offset: 1px;
}
.explorer-tbl {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}
.explorer-tbl th {
  background: #f1f7ff;
  color: #0b3668;
  padding: 0.5rem 0.75rem;
  border-bottom: 2px solid #c3cfe7;
  font-weight: 600;
  text-align: start;
  white-space: nowrap;
}
.explorer-tbl td {
  padding: 0.45rem 0.75rem;
  border-bottom: 1px solid #eef2fa;
  color: #0c3058;
  vertical-align: top;
  white-space: nowrap;
  max-width: 28ch;
  overflow: hidden;
  text-overflow: ellipsis;
}
.explorer-tbl tbody tr:hover td {
  background: #f1f7ff;
}
.th-sort {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  background: none;
  border: 0;
  padding: 0;
  font: inherit;
  color: inherit;
  cursor: pointer;
  white-space: nowrap;
}
.th-sort:hover {
  color: #0068f5;
}
.th-sort:focus-visible {
  outline: 2px solid #0068f5;
  outline-offset: 1px;
  border-radius: 0.2rem;
}
.th-sort-arrow {
  font-size: 0.65em;
  opacity: 0.35;
}
.th-sort--active .th-sort-arrow {
  opacity: 1;
  color: #0068f5;
}
.explorer-state {
  padding: 1.5rem;
  text-align: center;
  color: #6c757d;
  font-size: 0.9rem;
  white-space: normal;
  max-width: none;
}
.explorer-state--error {
  color: #dc3545;
}
.explorer-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  border: 1px solid #c3cfe7;
  border-radius: 50rem;
  padding: 0.25rem 0.75rem;
  background: #fff;
  color: #0c3058;
  font-family: Rubik, sans-serif;
  font-size: 0.8rem;
  cursor: pointer;
}
.explorer-pill:hover {
  background: #f1f7ff;
}
.explorer-pill--active {
  background: #0068f5;
  border-color: #0068f5;
  color: #fff;
}
.explorer-pill-fmt {
  font-size: 0.65rem;
  font-weight: 600;
  opacity: 0.75;
}
.explorer-skel {
  display: block;
  height: 1rem;
  margin: 0.5rem 0;
  background: linear-gradient(90deg, #f1f7ff 0%, #e7eef9 50%, #f1f7ff 100%);
  background-size: 200% 100%;
  border-radius: 0.2rem;
  animation: explorer-pulse 1.4s ease-in-out infinite;
}
@keyframes explorer-pulse {
  0% { background-position: 100% 0; }
  100% { background-position: -100% 0; }
}
</style>
