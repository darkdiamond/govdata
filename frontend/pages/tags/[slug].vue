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

useHead(() => ({
  title: `${slug.value} — GovData.IL`,
  meta: [{ name: 'description', content: `מאגרי מידע עם התגית "${slug.value}"` }],
}))
</script>

<template>
  <div class="max-w-6xl mx-auto px-4 py-8">
    <section class="mb-6">
      <div class="text-xs text-subtle mb-2">
        <NuxtLink to="/">ראשי</NuxtLink> ›
        <NuxtLink to="/tags/">נושאים</NuxtLink> ›
        {{ slug }}
      </div>
      <h1 class="font-display text-3xl">תגית: {{ slug }}</h1>
      <p class="text-subtle mt-2">{{ entries.length }} מאגרים</p>
    </section>

    <section class="grid grid-cols-1 md:grid-cols-2 gap-3">
      <DatasetCard v-for="e in entries" :key="e.id" :entry="e" />
    </section>
  </div>
</template>
