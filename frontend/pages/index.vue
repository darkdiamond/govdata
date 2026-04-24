<script setup lang="ts">
import { useFacets, useManifest } from '~/composables/useManifest'
import type { ManifestEntry } from '~/types/manifest'

useHead({ title: 'GovData.IL — מידע ממשלתי פתוח' })

const manifest = useManifest()
const datasets = computed<ManifestEntry[]>(() => manifest.value?.datasets ?? [])
const { organizations, formats } = useFacets(datasets.value)

const orgFilter = ref<string | null>(null)
const formatFilter = ref<string | null>(null)

const filtered = computed<ManifestEntry[]>(() =>
  datasets.value.filter((d) => {
    if (orgFilter.value && d.organization !== orgFilter.value) return false
    if (formatFilter.value && !d.formats.includes(formatFilter.value)) return false
    return true
  }),
)

function clear() {
  orgFilter.value = null
  formatFilter.value = null
}
</script>

<template>
  <div class="max-w-6xl mx-auto px-4 py-8">
    <section class="mb-8">
      <h1 class="font-display text-3xl">חיפוש והבנה של מאגרי המידע של ממשלת ישראל</h1>
      <p class="text-subtle mt-2 max-w-2xl">
        אוספים מידע ציבורי מ-data.gov.il, מייצרים תקציר AI, תובנות וויזואליזציות אוטומטיות לכל מאגר.
      </p>
    </section>

    <section class="grid grid-cols-1 lg:grid-cols-[1fr_260px] gap-8">
      <div>
        <div class="flex items-center justify-between mb-3 text-sm">
          <span class="text-subtle">{{ filtered.length }} מאגרים זמינים</span>
          <button
            v-if="orgFilter || formatFilter"
            @click="clear"
            class="text-brand hover:underline"
          >
            איפוס פילטרים
          </button>
        </div>

        <div v-if="datasets.length === 0" class="card p-6 text-center text-subtle">
          <p class="m-0">עדיין לא נוצרו דפים. הפעל את הסורק + ה-page-builder כדי להתחיל.</p>
        </div>

        <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-3">
          <a
            v-for="d in filtered"
            :key="d.id"
            :href="`/datasets/${d.id}/`"
            class="card card-hover p-4 no-underline hover:no-underline block"
          >
            <div class="flex gap-2 flex-wrap mb-2 text-xs">
              <span v-if="d.organization" class="badge">{{ d.organization }}</span>
              <span v-for="f in d.formats.slice(0, 3)" :key="f" class="badge">{{ f }}</span>
            </div>
            <h3 class="font-display text-ink m-0 mb-2">{{ d.title }}</h3>
            <p v-if="d.summary_he" class="text-sm text-subtle leading-relaxed line-clamp-2 m-0">
              {{ d.summary_he }}
            </p>
            <div class="text-xs text-subtle mt-2">
              עודכן {{ relativeTimeHe(d.metadata_modified) }}
            </div>
          </a>
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
