<script setup lang="ts">
import { useManifest } from '~/composables/useManifest'

useHead({ title: 'משרדים — GovData.IL' })

const manifest = useManifest()

interface MinistryRow {
  slug: string
  title: string
  count: number
}

const ministries = computed<MinistryRow[]>(() => {
  const by = new Map<string, MinistryRow>()
  for (const d of manifest.value?.datasets ?? []) {
    if (!d.organization_slug || !d.organization) continue
    const row = by.get(d.organization_slug)
    if (row) row.count++
    else by.set(d.organization_slug, {
      slug: d.organization_slug, title: d.organization, count: 1,
    })
  }
  return [...by.values()].sort((a, b) => b.count - a.count)
})
</script>

<template>
  <div class="max-w-6xl mx-auto px-4 py-8">
    <section class="mb-6">
      <div class="text-xs text-subtle mb-2">
        <NuxtLink to="/">ראשי</NuxtLink> › משרדים
      </div>
      <h1 class="font-display text-3xl">משרדים ממשלתיים</h1>
      <p class="text-subtle mt-2 max-w-2xl">{{ ministries.length }} ארגונים מפרסמים מאגרי מידע ציבורי.</p>
    </section>

    <section class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
      <NuxtLink
        v-for="m in ministries"
        :key="m.slug"
        :to="`/ministries/${m.slug}/`"
        class="card card-hover p-4 no-underline hover:no-underline block"
      >
        <div class="font-display text-ink">{{ m.title }}</div>
        <div class="text-xs text-subtle mt-1">{{ m.count }} מאגרים</div>
      </NuxtLink>
    </section>
  </div>
</template>
