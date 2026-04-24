<script setup lang="ts">
const route = useRoute()
const onHome = computed(() => route.path === '/')
</script>

<template>
  <div class="min-h-screen flex flex-col">
    <header class="bg-white border-b border-rule">
      <div class="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between gap-6">
        <NuxtLink to="/" class="flex items-center gap-2 no-underline hover:no-underline">
          <span class="w-8 h-8 rounded-md bg-brand grid place-items-center text-white text-sm font-display">
            GD
          </span>
          <span class="font-display text-lg text-ink">GovData.IL</span>
        </NuxtLink>
        <nav class="flex items-center gap-6 text-sm">
          <NuxtLink
            to="/"
            class="text-subtle hover:text-brand-500"
            :class="{ 'text-brand-500 font-medium': onHome }"
          >
            ראשי
          </NuxtLink>
          <NuxtLink to="/ministries/" class="text-subtle hover:text-brand-500">משרדים</NuxtLink>
          <NuxtLink to="/tags/" class="text-subtle hover:text-brand-500">נושאים</NuxtLink>
        </nav>
      </div>
    </header>

    <main class="flex-1">
      <slot />
    </main>

    <footer class="bg-white border-t border-rule mt-16">
      <div class="max-w-6xl mx-auto px-4 py-6 text-xs text-subtle flex flex-col sm:flex-row sm:justify-between gap-2">
        <div>
          תוכן שנוצר אוטומטית ממידע ציבורי.
          מקור:
          <a href="https://data.gov.il" target="_blank" rel="noopener">data.gov.il</a>
        </div>
        <div>© {{ new Date().getFullYear() }} GovData.IL</div>
      </div>
    </footer>
  </div>
</template>
