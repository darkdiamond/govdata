<script setup lang="ts">
import { useManifest } from '~/composables/useManifest'

useSeo({
  title: 'מאגרי מידע ממשלתיים לפי נושא',
  description: 'כל התגיות והנושאים שמופיעים במאגרי המידע של ממשלת ישראל. דפדפו לפי נושא לאיתור מאגרים רלוונטיים.',
  path: '/tags/',
  breadcrumbs: [
    { name: 'ראשי', url: 'https://govil.ai/' },
    { name: 'נושאים', url: 'https://govil.ai/tags/' },
  ],
})

const manifest = useManifest()

const tags = computed(() => {
  const counts = new Map<string, number>()
  for (const d of manifest.value?.datasets ?? []) {
    for (const t of d.tags_he) counts.set(t, (counts.get(t) ?? 0) + 1)
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1])
})

const tagSlugs = computed(() => manifest.value?.tag_slugs ?? {})

function tagHref(t: string): string {
  const slug = tagSlugs.value[t] ?? t
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
        v-for="[t, n] in tags"
        :key="t"
        :to="tagHref(t)"
        class="tag-chip hover:bg-brand-100 no-underline hover:no-underline inline-flex items-center gap-1.5"
      >
        <img src="/icons/tag.svg" alt="" class="w-3.5 h-3.5 opacity-80" />
        {{ t }} <span class="text-subtle ms-1">· {{ n }}</span>
      </NuxtLink>
    </section>
  </div>
</template>
