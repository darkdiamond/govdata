<script setup lang="ts">
// Hero. AI-forward brand (gov-il.ai), benefit-led headline + subtitle.
// No tech-stack names visible — just value.
</script>

<template>
  <section class="relative overflow-hidden">
    <div class="absolute inset-0 -z-10">
      <div class="absolute inset-0 bg-gradient-to-b from-brand-50 via-white to-surface"></div>
      <div class="absolute -top-32 end-[-8%] w-[560px] h-[560px] rounded-full bg-brand/10 blur-3xl"></div>
      <div class="absolute top-40 start-[-10%] w-[320px] h-[320px] rounded-full bg-brand/5 blur-3xl"></div>
    </div>

    <div class="py-14 md:py-24">
      <span class="inline-flex items-center gap-2 px-3 py-1 rounded-gov-pill bg-white border border-rule text-xs text-brand-700 shadow-card">
        <span aria-hidden="true">✨</span>
        gov-il.ai · מופעל על ידי סוכני AI
      </span>

      <h1 class="font-display mt-5 max-w-4xl text-[clamp(2rem,1.4rem+3vw,3.25rem)] leading-[1.15]">
        מידע ממשלתי פתוח,<br class="hidden md:block">
        מובן ומקושר — <span class="text-brand-700">על ידי AI</span>
      </h1>

      <p class="mt-5 max-w-2xl text-lg md:text-xl text-ink/80 leading-relaxed">
        כל מאגר שפרסמה הממשלה הופך לעמוד אחד בעברית: תקציר, ויזואליזציות, תובנות וקישורים.
        בלי להוריד קבצים, בלי לפתוח CSV, בלי ידע טכני — רק להבין את המידע ולשתף אותו עם כל אחד.
      </p>

      <div class="mt-7 flex flex-wrap items-center gap-3">
        <NuxtLink to="/datasets/" class="btn-primary text-base">
          <img src="/icons/database.svg" alt="" class="w-4 h-4 invert opacity-90" />
          גלה מאגרים
        </NuxtLink>
        <NuxtLink to="/how-it-works/" class="btn-ghost text-base">
          איך זה עובד?
          <img src="/icons/arrow-left.svg" alt="" class="w-4 h-4" />
        </NuxtLink>
      </div>

      <ul class="mt-10 grid grid-cols-2 md:grid-cols-4 gap-3 list-none p-0 m-0 text-xs sm:text-sm">
        <li class="flex items-center gap-2 text-ink/80">
          <img src="/icons/circle-check.svg" alt="" class="w-4 h-4 opacity-80" />
          ויזואליזציות אוטומטיות
        </li>
        <li class="flex items-center gap-2 text-ink/80">
          <img src="/icons/circle-check.svg" alt="" class="w-4 h-4 opacity-80" />
          תובנות מוכנות לשיתוף
        </li>
        <li class="flex items-center gap-2 text-ink/80">
          <img src="/icons/circle-check.svg" alt="" class="w-4 h-4 opacity-80" />
          מבוסס מקור ממשלתי רשמי
        </li>
        <li class="flex items-center gap-2 text-ink/80">
          <img src="/icons/circle-check.svg" alt="" class="w-4 h-4 opacity-80" />
          חינמי וזמין לכל אחד
        </li>
      </ul>
    </div>
  </section>
</template>
