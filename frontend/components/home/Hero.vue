<script setup lang="ts">
import { useManifest } from '~/composables/useManifest'

const manifest = useManifest()

const lastUpdatedMs = computed(() => {
  const generated = manifest.value?.generated_at
  return generated ? Date.parse(generated) : null
})

const relativeAgo = computed(() => formatRelativeHe(lastUpdatedMs.value))

function formatRelativeHe(ts: number | null): string {
  if (!ts) return ''
  const diffMs = Date.now() - ts
  const minutes = Math.round(diffMs / 60_000)
  if (minutes < 1) return 'הרגע'
  if (minutes < 60) return `לפני ${minutes} דק׳`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `לפני ${hours} שעות`
  const days = Math.round(hours / 24)
  if (days === 1) return 'אתמול'
  if (days < 7) return `לפני ${days} ימים`
  const weeks = Math.round(days / 7)
  if (weeks < 5) return `לפני ${weeks} שבועות`
  const months = Math.round(days / 30)
  return `לפני ${months} חודשים`
}

const heroFeatures = [
  'ויזואליזציות אוטומטיות',
  'תובנות מוכנות לשיתוף',
  'מבוסס מקור ממשלתי רשמי',
  'חינמי וזמין לכל אחד',
]
</script>

<template>
  <section class="relative overflow-hidden">
    <div class="absolute inset-0 -z-10">
      <div class="absolute inset-0 bg-gradient-to-b from-brand-50 via-white to-surface"></div>
      <div class="absolute -top-32 end-[-8%] w-[560px] h-[560px] rounded-full bg-brand/10 blur-3xl"></div>
      <div class="absolute top-40 start-[-10%] w-[320px] h-[320px] rounded-full bg-brand/5 blur-3xl"></div>
    </div>

    <div class="pt-14 md:pt-24 pb-6 md:pb-10">
      <div
        class="inline-flex items-center gap-2.5 ps-2 pe-4 py-1.5 rounded-gov-pill
               bg-white/95 border border-brand-100 shadow-card backdrop-blur-sm"
        role="status"
        :aria-label="`סוכן AI מנתח מאגרים ממשלתיים, עדכון אחרון ${relativeAgo}`"
      >
        <span class="relative flex h-2.5 w-2.5" aria-hidden="true">
          <span class="absolute inline-flex h-full w-full rounded-full bg-ok opacity-60 animate-ping"></span>
          <span class="relative inline-flex h-2.5 w-2.5 rounded-full bg-ok"></span>
        </span>
        <span class="text-[11px] font-semibold tracking-wider text-ok uppercase" aria-hidden="true">LIVE</span>
        <span class="h-3 w-px bg-rule" aria-hidden="true"></span>
        <span class="text-sm font-medium text-ink">
          סוכן AI מנתח מאגרים ממשלתיים
        </span>
        <span v-if="relativeAgo" class="hidden sm:inline text-xs text-ink/60">· עדכון אחרון {{ relativeAgo }}</span>
      </div>

      <h1 class="font-display font-semibold mt-6 max-w-4xl
                 text-[clamp(2.25rem,1.4rem+3.5vw,4rem)] leading-[1.05] tracking-tight text-ink">
        כל מאגר ממשלתי —
        <span class="md:block text-brand-700">מוסבר, מחובר, מובן.</span>{{ ' ' }}<span class="text-ink/55 font-normal">בעזרת AI.</span>
      </h1>

      <p class="mt-5 max-w-2xl text-lg md:text-2xl text-ink/85 leading-relaxed">
        סוכן בינה מלאכותית קורא את הנתונים בשבילך, בוחר את הוויזואליזציה הנכונה,
        ומפיק תקציר ותובנות מוכנות לשיתוף.
        בלי להוריד קבצים, בלי Excel, בלי ידע טכני.
      </p>

      <div class="mt-7 flex flex-wrap items-center gap-3">
        <NuxtLink to="/datasets/" class="btn-primary text-base md:text-lg shadow-card hover:shadow-card-hover transition">
          <img src="/icons/database.svg" alt="" class="w-4 h-4 invert opacity-90" />
          גלה מאגרים
        </NuxtLink>
        <NuxtLink to="/how-it-works/" class="btn-ghost text-base md:text-lg">
          איך זה עובד?
          <img src="/icons/arrow-left.svg" alt="" class="w-4 h-4" />
        </NuxtLink>
      </div>

      <ul class="mt-10 flex flex-wrap gap-2.5 list-none p-0 m-0">
        <li
          v-for="f in heroFeatures"
          :key="f"
          class="flex items-center gap-2 rounded-gov-pill bg-white border border-rule
                 ps-3 pe-4 py-2 text-sm sm:text-base font-medium text-ink shadow-card"
        >
          <img src="/icons/circle-check.svg" alt="" class="w-[18px] h-[18px] opacity-90" />
          {{ f }}
        </li>
      </ul>
    </div>
  </section>
</template>
