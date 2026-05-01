<script setup lang="ts">
import { useManifest } from '~/composables/useManifest'

const route = useRoute()
const slug = computed(() => decodeURIComponent(String(route.params.slug)))
const manifest = useManifest()

const entries = computed(() =>
  (manifest.value?.datasets ?? []).filter((d) => d.tags_he.includes(slug.value)),
)

if (entries.value.length === 0) {
  throw createError({ statusCode: 404, statusMessage: 'Tag not found', fatal: true })
}

const SITE_URL = 'https://gov-il.ai'
const tagDescription = computed(
  () => `${entries.value.length} מאגרי מידע ציבוריים מ-data.gov.il עם התגית "${slug.value}".`,
)

useSeo({
  title: `תגית: ${slug.value}`,
  description: tagDescription.value,
  path: `/tags/${encodeURIComponent(slug.value)}/`,
  keywords: [slug.value],
  breadcrumbs: [
    { name: 'ראשי', url: `${SITE_URL}/` },
    { name: 'נושאים', url: `${SITE_URL}/tags/` },
    { name: slug.value, url: `${SITE_URL}/tags/${encodeURIComponent(slug.value)}/` },
  ],
  extraJsonLd: {
    '@context': 'https://schema.org',
    '@type': 'CollectionPage',
    name: `מאגרים עם התגית "${slug.value}"`,
    inLanguage: 'he-IL',
    url: `${SITE_URL}/tags/${encodeURIComponent(slug.value)}/`,
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
        <NuxtLink to="/">ראשי</NuxtLink> ›
        <NuxtLink to="/tags/">נושאים</NuxtLink> ›
        {{ slug }}
      </div>
      <h1 class="font-display">תגית: {{ slug }}</h1>
      <p class="text-subtle mt-2">{{ entries.length }} מאגרים</p>
    </section>

    <section class="grid grid-cols-1 md:grid-cols-2 gap-3">
      <DatasetCard v-for="e in entries" :key="e.id" :entry="e" />
    </section>
  </div>
</template>
