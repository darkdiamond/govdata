<script setup lang="ts">
const benefits = [
  {
    icon: '/icons/info.svg',
    title: 'תקציר ברור, לא קובץ גולמי',
    body: 'במקום להוריד CSV, לפתוח אותו ולנחש מה כל עמודה אומרת — AI כותב תקציר קצר שמסביר מה המאגר, מה הוא מכיל ולמה זה חשוב.',
  },
  {
    icon: '/icons/map-pin.svg',
    title: 'ויזואליזציה אוטומטית',
    body: 'לכל מאגר נבחרת התצוגה המתאימה: מפה אינטראקטיבית, גרף זמן, רשימה מסוננת או טבלה. אין צורך ב-Excel ואין צורך להיות אנליסט.',
  },
  {
    icon: '/icons/circle-check.svg',
    title: 'תובנות מוכנות לשיתוף',
    body: 'הסוכן מזהה מגמות, נקודות קיצון והקשר רגולטורי ומנסח אותם בצורה ברורה. מתאים לעיתונאים, חוקרים, ולכל מי שרוצה להבין מה באמת קורה.',
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
      <h2 class="font-display font-semibold m-0 text-2xl md:text-4xl tracking-tight">
        המידע כבר שם.
        <span class="md:block text-brand-700">אנחנו עוזרים להבין מה הוא אומר.</span>
      </h2>
      <p class="mt-3 text-base md:text-lg text-ink/75 leading-relaxed">
        אלפי מאגרים ציבוריים מתפרסמים בכל שנה — דוחות, רישומים, קואורדינטות, מספרים.
        govil.ai הופך אותם לסיפור: תקציר ברור, גרפים מתאימים ותובנות שאפשר לשתף.
      </p>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-5">
      <div
        v-for="(b, i) in benefits"
        :key="i"
        class="card p-6 md:p-7 flex gap-4 items-start hover:shadow-card-hover hover:-translate-y-0.5 transition"
      >
        <div class="flex-none w-12 h-12 rounded-gov-pill bg-brand-50 ring-1 ring-brand-100 grid place-items-center">
          <img :src="b.icon" alt="" class="w-6 h-6 opacity-90" />
        </div>
        <div>
          <h3 class="font-display text-ink m-0 mb-1.5 text-lg md:text-xl font-semibold">{{ b.title }}</h3>
          <p class="text-base text-ink/75 leading-relaxed m-0">{{ b.body }}</p>
        </div>
      </div>
    </div>
  </section>
</template>
