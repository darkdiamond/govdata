<script setup lang="ts">
import { useKindLabels } from '~/composables/useKindLabels'
import type { DatasetKind } from '~/types/manifest'

// Counted by pages/index.vue's home payload.
const props = defineProps<{ kindCounts: Partial<Record<DatasetKind, number>> }>()

const { KIND_INFO, KIND_ORDER } = useKindLabels()

const tiles = computed(() =>
  KIND_ORDER
    .map((k) => ({ kind: k, info: KIND_INFO[k], count: props.kindCounts[k] ?? 0 }))
    .filter((t) => t.count > 0),
)
</script>

<template>
  <section v-if="tiles.length">
    <div class="flex items-baseline justify-between mb-6">
      <h2 class="font-display m-0">מאגרים לפי סוג מידע</h2>
    </div>

    <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
      <NuxtLink
        v-for="t in tiles"
        :key="t.kind"
        :to="`/kinds/${t.kind}/`"
        class="card card-hover p-4 no-underline hover:no-underline flex flex-col gap-2"
      >
        <img :src="t.info.icon" alt="" class="w-6 h-6 opacity-75" />
        <div class="font-display text-ink">{{ t.info.label }}</div>
        <div class="text-xs text-subtle">{{ t.info.blurb }}</div>
        <div class="text-xs text-brand-700 mt-auto">{{ t.count }} מאגרים ←</div>
      </NuxtLink>
    </div>
  </section>
</template>
