<script setup lang="ts">
import { useManifest } from '~/composables/useManifest'
import type { ManifestEntry } from '~/types/manifest'

const manifest = useManifest()

const latest = computed<ManifestEntry[]>(() => {
  const list = [...(manifest.value?.datasets ?? [])]
  list.sort((a, b) => {
    const ta = a.last_analyzed_at ? Date.parse(a.last_analyzed_at) : 0
    const tb = b.last_analyzed_at ? Date.parse(b.last_analyzed_at) : 0
    return tb - ta
  })
  return list.slice(0, 6)
})
</script>

<template>
  <section v-if="latest.length">
    <div class="flex items-baseline justify-between mb-6">
      <h2 class="font-display m-0">חדש באתר</h2>
      <NuxtLink to="/datasets/" class="text-sm text-brand-700 hover:underline">
        כל המאגרים ←
      </NuxtLink>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
      <DatasetCard v-for="e in latest" :key="e.id" :entry="e" />
    </div>
  </section>
</template>
