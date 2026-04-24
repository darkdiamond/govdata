<script setup lang="ts">
import { useManifest } from '~/composables/useManifest'

useHead({ title: 'נושאים — GovData.IL' })

const manifest = useManifest()

const tags = computed(() => {
  const counts = new Map<string, number>()
  for (const d of manifest.value?.datasets ?? []) {
    for (const t of d.tags_he) counts.set(t, (counts.get(t) ?? 0) + 1)
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1])
})
</script>

<template>
  <div class="max-w-6xl mx-auto px-4 py-8">
    <section class="mb-6">
      <div class="text-xs text-subtle mb-2">
        <NuxtLink to="/">ראשי</NuxtLink> › נושאים
      </div>
      <h1 class="font-display text-3xl">נושאים</h1>
      <p class="text-subtle mt-2">{{ tags.length }} תגיות ייחודיות.</p>
    </section>

    <section class="flex flex-wrap gap-2">
      <NuxtLink
        v-for="[t, n] in tags"
        :key="t"
        :to="`/tags/${encodeURIComponent(t)}/`"
        class="tag-chip hover:bg-brand-100 no-underline hover:no-underline"
      >
        {{ t }} <span class="text-subtle ms-1">· {{ n }}</span>
      </NuxtLink>
    </section>
  </div>
</template>
