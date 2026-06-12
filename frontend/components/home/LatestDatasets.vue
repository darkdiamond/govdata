<script setup lang="ts">
import type { SlimEntry } from '~/types/manifest'

// Sorted + sliced by pages/index.vue's home payload.
defineProps<{ latest: SlimEntry[] }>()
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
