<script setup lang="ts">
import { loadSearchIndex } from '~/utils/search-index'

useSeo({
  title: 'מאגרי מידע ממשלתיים לפי נושא',
  description: 'כל התגיות והנושאים שמופיעים במאגרי המידע של ממשלת ישראל. דפדפו לפי נושא לאיתור מאגרים רלוונטיים.',
  path: '/tags/',
  breadcrumbs: [
    { name: 'ראשי', url: 'https://govil.ai/' },
    { name: 'נושאים', url: 'https://govil.ai/tags/' },
  ],
})

// Bake only [tag, count, slug] rows into the payload — not the index itself.
const { data } = await useAsyncData('tags-index', async () => {
  const index = await loadSearchIndex()
  const counts = new Map<string, number>()
  for (const d of index.datasets) {
    // Union of CKAN-official tags and the agent's curated suggested_tags,
    // deduped per dataset so a tag that appears in both doesn't double-count.
    const seen = new Set<string>([...(d.tags_he ?? []), ...(d.suggested_tags ?? [])])
    for (const t of seen) counts.set(t, (counts.get(t) ?? 0) + 1)
  }
  const slugs = index.tag_slugs ?? {}
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([t, n]) => [t, n, slugs[t] ?? t] as [string, number, string])
})

const tags = computed(() => data.value ?? [])

function tagHref(slug: string): string {
  return `/tags/${encodeURI(slug)}/`
}
</script>

<template>
  <div class="max-w-gov mx-auto px-4 py-8">
    <section class="mb-6">
      <div class="text-xs text-subtle mb-2">
        <NuxtLink to="/">ראשי</NuxtLink> › נושאים
      </div>
      <h1 class="font-display">נושאים</h1>
      <p class="text-subtle mt-2">{{ tags.length }} תגיות ייחודיות.</p>
    </section>

    <section class="flex flex-wrap gap-2">
      <NuxtLink
        v-for="[t, n, slug] in tags"
        :key="t"
        :to="tagHref(slug)"
        class="tag-chip hover:bg-brand-100 no-underline hover:no-underline inline-flex items-center gap-1.5"
      >
        <img src="/icons/tag.svg" alt="" class="w-3.5 h-3.5 opacity-80" />
        {{ t }} <span class="text-subtle ms-1">· {{ n }}</span>
      </NuxtLink>
    </section>
  </div>
</template>
