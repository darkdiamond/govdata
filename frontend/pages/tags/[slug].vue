<script setup lang="ts">
import { buildDatasetLdSummary } from '~/composables/useDatasetLd'
import { useManifest } from '~/composables/useManifest'

const route = useRoute()
const slug = computed(() => String(route.params.slug))
const manifest = useManifest()

// Resolve the URL slug back to its Hebrew tag via the publisher-built map.
// The map lives at the manifest top level; reverse-iterate to find the
// Hebrew key whose value matches our URL slug. Both directions are O(N) in
// the number of tags, which is small (low hundreds) so a precomputed
// reverse Map would be premature here.
const hebrewTag = computed<string | null>(() => {
  const map = manifest.value?.tag_slugs ?? {}
  for (const [he, latin] of Object.entries(map)) {
    if (latin === slug.value) return he
  }
  return null
})

const entries = computed(() => {
  const tag = hebrewTag.value
  if (!tag) return []
  return (manifest.value?.datasets ?? []).filter(
    (d) => d.tags_he.includes(tag) || (d.suggested_tags ?? []).includes(tag),
  )
})

if (!hebrewTag.value || entries.value.length === 0) {
  throw createError({ statusCode: 404, statusMessage: 'Tag not found', fatal: true })
}

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
