<script setup lang="ts">
// Two-up CTA strip that bridges the curated home to the content pages.
</script>

<template>
  <section class="grid grid-cols-1 md:grid-cols-2 gap-3">
    <NuxtLink
      to="/about/"
      class="card card-hover p-6 no-underline hover:no-underline block"
    >
      <div class="text-xs text-brand-700 mb-2">אודות</div>
      <div class="font-display text-lg text-ink mb-1">על הפרויקט</div>
      <p class="text-sm text-subtle leading-relaxed m-0">
        למי זה מתאים, מה הופך את govil.ai לשונה, וכיצד אנו מנגישים את המידע הממשלתי לכל אחד.
      </p>
    </NuxtLink>

    <NuxtLink
      to="/faq/"
      class="card card-hover p-6 no-underline hover:no-underline block"
    >
      <div class="text-xs text-brand-700 mb-2">שאלות נפוצות</div>
      <div class="font-display text-lg text-ink mb-1">שאלות ותשובות</div>
      <p class="text-sm text-subtle leading-relaxed m-0">
        האם התוכן מדויק? איך מציעים מאגר חדש? כל מה שחשוב לדעת.
      </p>
    </NuxtLink>
  </section>
</template>
