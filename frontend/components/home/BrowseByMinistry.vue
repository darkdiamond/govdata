<script setup lang="ts">
interface Row { slug: string; title: string; count: number }

// Aggregated + sliced by pages/index.vue's home payload.
const props = defineProps<{ ministries: Row[] }>()

const top = computed<Row[]>(() => props.ministries.slice(0, 6))
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
