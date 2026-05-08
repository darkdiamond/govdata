<script setup lang="ts">
import { useManifest } from '~/composables/useManifest'

interface Row { slug: string; title: string; count: number }

const manifest = useManifest()

const top = computed<Row[]>(() => {
  const by = new Map<string, Row>()
  for (const d of manifest.value?.datasets ?? []) {
    if (!d.organization_slug || !d.organization) continue
    const r = by.get(d.organization_slug)
    if (r) r.count++
    else by.set(d.organization_slug, { slug: d.organization_slug, title: d.organization, count: 1 })
  }
  return [...by.values()].sort((a, b) => b.count - a.count).slice(0, 6)
})
</script>

<template>
  <section v-if="top.length">
    <div class="flex items-baseline justify-between mb-6">
      <h2 class="font-display m-0">מאגרים לפי משרד</h2>
      <NuxtLink to="/ministries/" class="text-sm text-brand-700 hover:underline">
        כל המשרדים ←
      </NuxtLink>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
      <NuxtLink
        v-for="m in top"
        :key="m.slug"
        :to="`/ministries/${m.slug}/`"
        class="card card-hover p-4 no-underline hover:no-underline flex items-start gap-3"
      >
        <img src="/icons/building-2.svg" alt="" class="w-5 h-5 mt-0.5 opacity-70" />
        <div>
          <div class="font-display text-ink">{{ m.title }}</div>
          <div class="text-xs text-subtle mt-1">{{ m.count }} מאגרים</div>
        </div>
      </NuxtLink>
    </div>
  </section>
</template>
