<script setup lang="ts">
// Benefit-led audience strip. Not a step-by-step — a "what changes for you"
// pitch, separate from the HowItWorks pipeline story.
const benefits = [
  {
    icon: '/icons/info.svg',
    title: 'תקציר בעברית, לא קובץ גולמי',
    body: 'במקום להוריד CSV, לפתוח אותו ולנחש מה כל עמודה אומרת — AI כותב תקציר קצר בעברית שמסביר מה המאגר, מה הוא מכיל ולמה זה חשוב.',
  },
  {
    icon: '/icons/map-pin.svg',
    title: 'ויזואליזציה אוטומטית',
    body: 'לכל מאגר נבחרת התצוגה המתאימה: מפה אינטראקטיבית, גרף זמן, רשימה מסוננת או טבלה. אין צורך ב-Excel ואין צורך להיות אנליסט.',
  },
  {
    icon: '/icons/circle-check.svg',
    title: 'תובנות מוכנות לשיתוף',
    body: 'הסוכן מזהה מגמות, נקודות קיצון והקשר רגולטורי ומנסח אותם בעברית ברורה. מתאים לעיתונאים, חוקרים, ולכל מי שרוצה להבין מה באמת קורה.',
  },
  {
    icon: '/icons/tag.svg',
    title: 'מאגרים מחוברים זה לזה',
    body: 'כל דף מציע מאגרים קשורים מתוך אלפי המאגרים הממשלתיים — כדי שתוכל לעבור מנושא אחד לשני בלי לחפש מחדש.',
  },
]
</script>

<template>
  <section>
    <div class="mb-8 max-w-3xl">
      <h2 class="font-display m-0">הנגשה, לא רק פרסום</h2>
      <p class="mt-2 text-ink/75 leading-relaxed">
        מידע ממשלתי רשמי כבר זמין — אבל עד היום הוא נגיש רק למי שיודע לפתוח CSV ולקרוא טבלאות באנגלית. gov-il.ai סוגר את הפער.
      </p>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
      <div
        v-for="(b, i) in benefits"
        :key="i"
        class="card p-5 flex gap-4 items-start"
      >
        <div class="flex-none w-10 h-10 rounded-gov-pill bg-brand-50 grid place-items-center">
          <img :src="b.icon" alt="" class="w-5 h-5 opacity-80" />
        </div>
        <div>
          <h3 class="font-display text-ink m-0 mb-1 text-base">{{ b.title }}</h3>
          <p class="text-sm text-ink/75 leading-relaxed m-0">{{ b.body }}</p>
        </div>
      </div>
    </div>
  </section>
</template>
