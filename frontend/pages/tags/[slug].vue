<script setup lang="ts">
import { buildDatasetLdSummary } from '~/composables/useDatasetLd'
import { loadSearchIndex } from '~/utils/search-index'

const route = useRoute()
const slug = computed(() => String(route.params.slug))

// Resolve the URL slug back to its Hebrew tag via the publisher-built map,
// then bake only this tag's slim entries into the page payload (the key
// must include the slug — colliding keys would cross-pollinate payloads).
const { data } = await useAsyncData(`tag-${slug.value}`, async () => {
  const index = await loadSearchIndex()
  const map = index.tag_slugs ?? {}
  let hebrewTag: string | null = null
  for (const [he, latin] of Object.entries(map)) {
    if (latin === slug.value) {
      hebrewTag = he
      break
    }
  }
  if (!hebrewTag) return null
  const entries = index.datasets.filter(
    (d) => d.tags_he.includes(hebrewTag!) || (d.suggested_tags ?? []).includes(hebrewTag!),
  )
  return { hebrewTag, entries }
})

if (!data.value || data.value.entries.length === 0) {
  throw createError({ statusCode: 404, statusMessage: 'Tag not found', fatal: true })
}

const hebrewTag = computed(() => data.value!.hebrewTag)
const entries = computed(() => data.value!.entries)

const SITE_URL = 'https://govil.ai'
const tagDescription = computed(
  () => `${entries.value.length} מאגרי מידע ציבוריים מ-data.gov.il עם התגית "${hebrewTag.value}".`,
)
const encodedSlug = computed(() => encodeURI(slug.value))
const canonicalUrl = computed(() => `${SITE_URL}/tags/${encodedSlug.value}/`)

useSeo({
  title: `מאגרי מידע ממשלתיים בנושא ${hebrewTag.value}`,
  description: tagDescription.value,
  path: `/tags/${encodedSlug.value}/`,
  keywords: hebrewTag.value ? [hebrewTag.value] : [],
  breadcrumbs: [
    { name: 'ראשי', url: `${SITE_URL}/` },
    { name: 'נושאים', url: `${SITE_URL}/tags/` },
    { name: hebrewTag.value!, url: canonicalUrl.value },
  ],
  extraJsonLd: {
    '@context': 'https://schema.org',
    '@type': 'CollectionPage',
    name: `מאגרים עם התגית "${hebrewTag.value}"`,
    inLanguage: 'he-IL',
    url: canonicalUrl.value,
    hasPart: entries.value.slice(0, 25).map(buildDatasetLdSummary),
  },
})
</script>

<template>
  <div class="max-w-gov mx-auto px-4 py-8">
    <section class="mb-6">
      <div class="text-xs text-subtle mb-2">
        <NuxtLink to="/">ראשי</NuxtLink> ›
        <NuxtLink to="/tags/">נושאים</NuxtLink> ›
        {{ hebrewTag }}
      </div>
      <h1 class="font-display">תגית: {{ hebrewTag }}</h1>
      <p class="text-subtle mt-2">{{ entries.length }} מאגרים</p>
    </section>

    <section class="grid grid-cols-1 md:grid-cols-2 gap-3">
      <DatasetCard v-for="e in entries" :key="e.id" :entry="e" />
    </section>
  </div>
</template>
