<script setup lang="ts">
import { useManifest } from '~/composables/useManifest'

const KIND_LABELS: Record<string, string> = {
  map: 'גיאוגרפי',
  timeseries: 'סדרת זמן',
  registry: 'רשימת ישויות',
  rankings: 'דירוגים',
  misc: 'אחר',
}

const route = useRoute()
const kind = computed(() => String(route.params.kind))
const manifest = useManifest()

const entries = computed(() =>
  (manifest.value?.datasets ?? []).filter((d) => d.dataset_kind === kind.value),
)
const label = computed(() => KIND_LABELS[kind.value] ?? kind.value)

if (entries.value.length === 0) {
  throw createError({ statusCode: 404, statusMessage: 'Kind not found', fatal: true })
}

const SITE_URL = 'https://govil.ai'
const kindDescription = computed(
  () => `${entries.value.length} מאגרי מידע ציבוריים מסוג ${label.value} — עם ויזואליזציות מתאימות.`,
)

useSeo({
  title: `מאגרי ${label.value} — מידע ממשלתי פתוח עם תקציר AI`,
  description: kindDescription.value,
  path: `/kinds/${kind.value}/`,
  keywords: [label.value],
  breadcrumbs: [
    { name: 'ראשי', url: `${SITE_URL}/` },
    { name: 'מאגרים', url: `${SITE_URL}/datasets/` },
    { name: label.value, url: `${SITE_URL}/kinds/${kind.value}/` },
  ],
  extraJsonLd: {
    '@context': 'https://schema.org',
    '@type': 'CollectionPage',
    name: `מאגרים מסוג ${label.value}`,
    inLanguage: 'he-IL',
    url: `${SITE_URL}/kinds/${kind.value}/`,
    hasPart: entries.value.slice(0, 25).map((e) => ({
      '@type': 'Dataset',
      name: e.title,
      url: `${SITE_URL}/datasets/${e.id}/`,
    })),
  },
})
</script>

<template>
  <div class="max-w-gov mx-auto px-4 py-8">
    <section class="mb-6">
      <div class="text-xs text-subtle mb-2">
        <NuxtLink to="/">ראשי</NuxtLink> › סוג: {{ label }}
      </div>
      <h1 class="font-display">{{ label }}</h1>
      <p class="text-subtle mt-2">{{ entries.length }} מאגרים</p>
    </section>

    <section class="grid grid-cols-1 md:grid-cols-2 gap-3">
      <DatasetCard v-for="e in entries" :key="e.id" :entry="e" />
    </section>
  </div>
</template>
