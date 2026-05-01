<script setup lang="ts">
import Fuse from 'fuse.js'
import { useManifest } from '~/composables/useManifest'
import type { ManifestEntry } from '~/types/manifest'

const router = useRouter()
const manifest = useManifest()
const open = ref(false)
const query = ref('')
const highlight = ref(-1)
const buttonEl = ref<HTMLElement | null>(null)
const inputEl = ref<HTMLInputElement | null>(null)
const panelEl = ref<HTMLElement | null>(null)

const fuse = computed(
  () =>
    new Fuse<ManifestEntry>(manifest.value?.datasets ?? [], {
      keys: [
        { name: 'title', weight: 0.5 },
        { name: 'summary_he', weight: 0.25 },
        { name: 'organization', weight: 0.15 },
        { name: 'tags_he', weight: 0.1 },
      ],
      threshold: 0.4,
      distance: 100,
      includeScore: false,
      minMatchCharLength: 2,
      ignoreLocation: true,
    }),
)

const results = computed<ManifestEntry[]>(() => {
  const q = query.value.trim()
  if (q.length < 2) return []
  return fuse.value.search(q, { limit: 6 }).map((r) => r.item)
})

watch(results, () => {
  highlight.value = results.value.length > 0 ? 0 : -1
})

function toggle() {
  open.value = !open.value
  if (open.value) nextTick(() => inputEl.value?.focus())
}

function close() {
  open.value = false
  highlight.value = -1
  buttonEl.value?.focus()
}

function go(entry: ManifestEntry) {
  open.value = false
  query.value = ''
  router.push(`/datasets/${entry.id}/`)
}

function submit() {
  const q = query.value.trim()
  if (highlight.value >= 0 && results.value[highlight.value]) {
    go(results.value[highlight.value])
    return
  }
  if (q) {
    open.value = false
    query.value = ''
    router.push({ path: '/datasets/', query: { q } })
  }
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    e.preventDefault()
    close()
    return
  }
  if (!results.value.length) return
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    highlight.value = (highlight.value + 1) % results.value.length
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    highlight.value = highlight.value <= 0 ? results.value.length - 1 : highlight.value - 1
  }
}

function onDocumentClick(e: MouseEvent) {
  if (!open.value) return
  const t = e.target as Node
  if (panelEl.value?.contains(t) || buttonEl.value?.contains(t)) return
  open.value = false
}

onMounted(() => {
  document.addEventListener('mousedown', onDocumentClick)
})
onBeforeUnmount(() => {
  document.removeEventListener('mousedown', onDocumentClick)
})
</script>

<template>
  <div class="relative">
    <button
      ref="buttonEl"
      type="button"
      :aria-label="open ? 'סגירת חיפוש' : 'פתיחת חיפוש'"
      :aria-expanded="open"
      aria-haspopup="dialog"
      class="inline-flex items-center gap-2 ps-2 pe-3 sm:ps-3 sm:pe-4 h-9 rounded-gov-pill bg-white/10 hover:bg-white/20 border border-white/20 text-white text-sm transition-colors"
      @click="toggle"
    >
      <img src="/icons/search.svg" alt="" class="w-4 h-4 invert opacity-90" />
      <span class="hidden sm:inline">חיפוש</span>
    </button>

    <div
      v-if="open"
      ref="panelEl"
      role="dialog"
      aria-label="חיפוש מאגרים"
      class="absolute top-full mt-2 end-0 w-[min(22rem,calc(100vw-2rem))] bg-white text-ink rounded-gov shadow-card border border-rule overflow-hidden z-50"
    >
      <label class="flex items-center gap-2 border-b border-rule px-3 py-2">
        <img src="/icons/search.svg" alt="" class="w-5 h-5 opacity-70" />
        <input
          ref="inputEl"
          v-model="query"
          type="search"
          placeholder="חיפוש מאגר, נושא או משרד…"
          class="flex-1 bg-transparent border-0 outline-none text-sm placeholder:text-subtle"
          @keydown="onKeydown"
          @keydown.enter.prevent="submit"
        />
      </label>

      <ul
        v-if="results.length"
        class="list-none m-0 p-0 max-h-80 overflow-y-auto"
      >
        <li v-for="(r, i) in results" :key="r.id">
          <button
            type="button"
            class="w-full text-start px-3 py-2 flex flex-col gap-0.5 hover:bg-brand-50 focus:bg-brand-50 outline-none transition-colors"
            :class="{ 'bg-brand-50': i === highlight }"
            @click="go(r)"
            @mouseenter="highlight = i"
          >
            <span class="text-sm text-ink truncate">{{ r.title }}</span>
            <span v-if="r.organization" class="text-xs text-subtle truncate">{{ r.organization }}</span>
          </button>
        </li>
      </ul>

      <div
        v-else-if="query.trim().length >= 2"
        class="px-3 py-4 text-sm text-subtle text-center"
      >
        אין תוצאות
      </div>

      <div
        v-else
        class="px-3 py-3 text-xs text-subtle"
      >
        התחילו להקליד שם מאגר, נושא או משרד.
      </div>

      <div class="border-t border-rule px-3 py-2 text-xs text-subtle bg-surface flex items-center justify-between gap-2">
        <span>הקשה על Enter תפתח את כל התוצאות</span>
        <NuxtLink
          to="/datasets/"
          class="text-brand-700 hover:underline no-underline"
          @click="open = false"
        >
          לכל המאגרים
        </NuxtLink>
      </div>
    </div>
  </div>
</template>
