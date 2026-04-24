<script setup lang="ts">
const route = useRoute()
const onHome = computed(() => route.path === '/')
const year = new Date().getFullYear()
</script>

<template>
  <div class="min-h-screen flex flex-col bg-surface">
    <header class="gov-header">
      <div class="max-w-gov mx-auto px-4 h-header flex items-center justify-between gap-6">
        <NuxtLink to="/" class="flex items-center gap-3 no-underline hover:no-underline text-white">
          <span class="w-9 h-9 rounded-gov bg-white/15 grid place-items-center text-white text-base font-display">
            .ai
          </span>
          <span class="font-display text-lg leading-none">gov-il.ai</span>
        </NuxtLink>

        <nav class="hidden md:flex items-center gap-6 text-sm">
          <NuxtLink
            to="/"
            class="text-white/85 hover:text-white no-underline hover:no-underline"
            :class="{ 'text-white font-medium': onHome }"
          >ראשי</NuxtLink>
          <NuxtLink to="/datasets/" class="text-white/85 hover:text-white no-underline hover:no-underline">מאגרים</NuxtLink>
          <NuxtLink to="/ministries/" class="text-white/85 hover:text-white no-underline hover:no-underline">משרדים</NuxtLink>
          <NuxtLink to="/tags/" class="text-white/85 hover:text-white no-underline hover:no-underline">נושאים</NuxtLink>
          <NuxtLink to="/how-it-works/" class="text-white/85 hover:text-white no-underline hover:no-underline">איך זה עובד</NuxtLink>
          <NuxtLink to="/about/" class="text-white/85 hover:text-white no-underline hover:no-underline">אודות</NuxtLink>
        </nav>

        <div class="flex items-center gap-3">
          <a
            href="https://data.gov.il"
            target="_blank"
            rel="noopener"
            class="hidden sm:inline-flex items-center gap-2 text-xs text-white/85 hover:text-white no-underline hover:no-underline"
          >
            <img src="/icons/external-link.svg" alt="" class="w-4 h-4" />
            data.gov.il
          </a>
          <button
            type="button"
            aria-label="חיפוש"
            class="w-9 h-9 grid place-items-center rounded-gov-pill hover:bg-white/10 transition-colors"
          >
            <img src="/icons/search.svg" alt="" class="w-5 h-5 invert opacity-90" />
          </button>
        </div>
      </div>
    </header>

    <main class="flex-1">
      <slot />
    </main>

    <footer class="bg-ink-deep text-white mt-16">
      <div class="max-w-gov mx-auto px-4 py-10 grid grid-cols-1 md:grid-cols-3 gap-8 text-sm">
        <div>
          <div class="font-display text-base mb-2">gov-il.ai</div>
          <p class="text-white/75 leading-relaxed m-0">
            מאגרי המידע הציבוריים של ממשלת ישראל — נגישים בעברית, מוסברים על ידי AI,
            פתוחים לכל אחד.
          </p>
        </div>
        <div>
          <div class="font-display text-base mb-2">ניווט</div>
          <ul class="list-none p-0 m-0 space-y-1.5">
            <li><NuxtLink to="/" class="text-white/85 hover:text-white no-underline hover:no-underline">ראשי</NuxtLink></li>
            <li><NuxtLink to="/datasets/" class="text-white/85 hover:text-white no-underline hover:no-underline">כל המאגרים</NuxtLink></li>
            <li><NuxtLink to="/ministries/" class="text-white/85 hover:text-white no-underline hover:no-underline">משרדים</NuxtLink></li>
            <li><NuxtLink to="/tags/" class="text-white/85 hover:text-white no-underline hover:no-underline">נושאים</NuxtLink></li>
            <li><NuxtLink to="/how-it-works/" class="text-white/85 hover:text-white no-underline hover:no-underline">איך זה עובד</NuxtLink></li>
            <li><NuxtLink to="/about/" class="text-white/85 hover:text-white no-underline hover:no-underline">אודות</NuxtLink></li>
            <li><NuxtLink to="/faq/" class="text-white/85 hover:text-white no-underline hover:no-underline">שאלות נפוצות</NuxtLink></li>
          </ul>
        </div>
        <div>
          <div class="font-display text-base mb-2">מקור</div>
          <ul class="list-none p-0 m-0 space-y-1.5 text-white/85">
            <li>
              <a href="https://data.gov.il" target="_blank" rel="noopener" class="inline-flex items-center gap-1.5 hover:text-white no-underline hover:no-underline">
                <img src="/icons/external-link.svg" alt="" class="w-4 h-4 invert opacity-90" />
                data.gov.il
              </a>
            </li>
            <li>
              <a href="https://www.gov.il" target="_blank" rel="noopener" class="inline-flex items-center gap-1.5 hover:text-white no-underline hover:no-underline">
                <img src="/icons/external-link.svg" alt="" class="w-4 h-4 invert opacity-90" />
                gov.il
              </a>
            </li>
          </ul>
        </div>
      </div>
      <div class="border-t border-white/10">
        <div class="max-w-gov mx-auto px-4 py-4 text-xs text-white/70 flex flex-col sm:flex-row sm:justify-between gap-2">
          <div>תוכן שנוצר אוטומטית על ידי AI ממידע ציבורי.</div>
          <div>© {{ year }} gov-il.ai</div>
        </div>
      </div>
    </footer>
  </div>
</template>
