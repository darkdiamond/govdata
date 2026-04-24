<script setup lang="ts">
import { useManifest } from '~/composables/useManifest'

const route = useRoute()
const slug = computed(() => String(route.params.slug))
const manifest = useManifest()

const entries = computed(() =>
  (manifest.value?.datasets ?? []).filter((d) => d.organization_slug === slug.value),
)
const ministryTitle = computed(() => entries.value[0]?.organization ?? slug.value)

if (entries.value.length === 0) {
  throw createError({ statusCode: 404, statusMessage: 'Ministry not found', fatal: true })
}

useHead(() => ({
  title: `${ministryTitle.value} — gov-il.ai`,
  meta: [{ name: 'description', content: `מאגרי המידע של ${ministryTitle.value}` }],
}))
</script>

<template>
  <div class="max-w-gov mx-auto px-4 py-8">
    <section class="mb-6">
      <div class="text-xs text-subtle mb-2">
        <NuxtLink to="/">ראשי</NuxtLink> ›
        <NuxtLink to="/ministries/">משרדים</NuxtLink> ›
        {{ ministryTitle }}
      </div>
      <h1 class="font-display">{{ ministryTitle }}</h1>
      <p class="text-subtle mt-2">{{ entries.length }} מאגרים</p>
    </section>

    <section class="grid grid-cols-1 md:grid-cols-2 gap-3">
      <DatasetCard v-for="e in entries" :key="e.id" :entry="e" />
    </section>
  </div>
</template>
