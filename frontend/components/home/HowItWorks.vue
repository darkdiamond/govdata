<script setup lang="ts">
// 4-step explainer. Each step: numbered badge + Hebrew title + one-line body.
// Copy is model-agnostic.
const steps = [
  {
    title: 'מזהים כל מאגר חדש',
    body: 'שירות ברקע עוקב באופן רציף אחר כל המאגרים שהממשלה מפרסמת, ומזהה כל מאגר חדש או עדכון שמגיע.',
  },
  {
    title: 'סוכן AI חוקר וכותב',
    body: 'סוכן אוטונומי קורא את הנתונים עצמם, מחפש ברשת הקשר רגולטורי ומנסח תקציר וויזואליזציות בעברית. מה שנכתב — מעוגן במקור, ללא הזיות.',
  },
  {
    title: 'מחברים מאגרים דומים',
    body: 'כל דף מציע מאגרים קרובים מבחינת משרד, נושא ותוכן — כדי שתוכלו לעבור מנושא אחד לשני בלי לחפש מחדש.',
  },
  {
    title: 'זמין מיד, בעברית, לכל אחד',
    body: 'הדף המוכן מתפרסם מיד ונגיש דרך הדפדפן — בלי התקנה, בלי רישום, ובלי שום ידע טכני.',
  },
]
</script>

<template>
  <section>
    <div class="flex items-baseline justify-between mb-6">
      <h2 class="font-display m-0">איך זה עובד?</h2>
      <NuxtLink to="/how-it-works/" class="text-sm text-brand-700 hover:underline">
        לקריאה מורחבת ←
      </NuxtLink>
    </div>

    <ol class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 list-none p-0 m-0">
      <li
        v-for="(s, i) in steps"
        :key="i"
        class="card p-5 flex flex-col gap-2"
      >
        <div class="w-8 h-8 rounded-gov-pill bg-brand-50 text-brand-700 font-display grid place-items-center text-sm">
          {{ i + 1 }}
        </div>
        <h3 class="font-display text-base text-ink m-0">{{ s.title }}</h3>
        <p class="text-sm text-subtle leading-relaxed m-0">{{ s.body }}</p>
      </li>
    </ol>
  </section>
</template>
