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

useHead(() => ({
  title: `${label.value} — GovData.IL`,
  meta: [{ name: 'description', content: `מאגרים מסוג ${label.value}` }],
}))
</script>

<template>
  <div class="max-w-6xl mx-auto px-4 py-8">
    <section class="mb-6">
      <div class="text-xs text-subtle mb-2">
        <NuxtLink to="/">ראשי</NuxtLink> › סוג: {{ label }}
      </div>
      <h1 class="font-display text-3xl">{{ label }}</h1>
      <p class="text-subtle mt-2">{{ entries.length }} מאגרים</p>
    </section>

    <section class="grid grid-cols-1 md:grid-cols-2 gap-3">
      <DatasetCard v-for="e in entries" :key="e.id" :entry="e" />
    </section>
  </div>
</template>
