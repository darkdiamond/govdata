<script setup lang="ts">
useSeo({
  title: 'איך זה עובד',
  description: 'כל דף ב-govil.ai נכתב אוטומטית על ידי סוכן AI — ללא עורך אנושי. הכירו את התהליך: זיהוי מאגר חדש, מחקר, כתיבה, ופרסום לעברית נגישה.',
  path: '/how-it-works/',
  keywords: ['agentic AI', 'סוכן AI אוטונומי', 'pipeline', 'איך עובד AI'],
  breadcrumbs: [
    { name: 'ראשי', url: 'https://govil.ai/' },
    { name: 'איך זה עובד', url: 'https://govil.ai/how-it-works/' },
  ],
})

const pipeline = [
  {
    title: 'מזהים כל מאגר חדש',
    body: 'שירות אוטומטי סורק באופן רציף את כל מקורות המידע הממשלתיים הרשמיים, ומאתר כל מאגר חדש או עדכון שמגיע. אין התערבות אנושית.',
  },
  {
    title: 'סוכן AI חוקר את הנתונים',
    body: 'הסוכן קורא את קובץ הנתונים עצמו — לא את כותרות העמודות בלבד. הוא מזהה דפוסים, מחפש ברשת הקשר רגולטורי או חדשותי, ומבין איזו תצוגה מתאימה למאגר הזה.',
  },
  {
    title: 'כותב דף הסבר',
    body: 'הסוכן מנסח תקציר, תובנות עיקריות וכותרות ברורות. הוא גם בוחר ויזואליזציה מתאימה — מפה, גרף זמן, רשימה או טבלה — ומפיק אותה באופן אינטראקטיבי בתוך הדף.',
  },
  {
    title: 'מפרסם, ממשיך לעדכן',
    body: 'הדף המוכן נגיש מיד בדפדפן — בלי התקנות ובלי רישום. כאשר המאגר מתעדכן במקור, הסוכן כותב מחדש את הדף כדי לשמור על נוכחות עדכנית.',
  },
]

const trust = [
  {
    title: 'אין הזיות',
    body: 'כל תקציר, מספר או תובנה מעוגנים במאגר המקורי או במקור ציבורי שהסוכן שלף בזמן הכתיבה. אם הסוכן לא מצליח לאמת פרט — הוא משאיר אותו בחוץ.',
  },
  {
    title: 'תמיד עם קישור למקור',
    body: 'כל דף שומר קישור ישיר לקובץ המקורי באתר הממשלתי הרשמי. אפשר תמיד להצליב את המספרים מול המקור — הוויזואליזציה היא פרשנות, המקור הוא האמת.',
  },
  {
    title: 'עדכון אוטומטי',
    body: 'כל שינוי במאגר המקורי — הוספת שורות, עדכון סטטוס, תיקון עמודה — מפעיל מחדש את הסוכן. כך הדפים לא מתיישנים.',
  },
  {
    title: 'פרטיות מלאה',
    body: 'האתר סטטי. אין cookies, אין tracking scripts, אין השלמה אוטומטית שמשתפת את החיפוש שלכם. מה שאתם קוראים נשאר בדפדפן שלכם.',
  },
]
</script>

<template>
  <div class="max-w-gov mx-auto px-4 py-8">
    <div class="text-xs text-subtle mb-2">
      <NuxtLink to="/">ראשי</NuxtLink> › איך זה עובד
    </div>

    <article class="max-w-4xl">
      <h1 class="font-display">איך govil.ai עובד</h1>
      <p class="mt-4 text-lg text-ink/80 leading-relaxed max-w-3xl">
        כל דף באתר נכתב <strong>אוטומטית לחלוטין</strong> על ידי סוכן AI —
        בלי שעורך אנושי יכתוב את התקציר, יבחר את הוויזואליזציה או ינסח את ההקשר.
        הנה מה שקורה מאחורי הקלעים.
      </p>

      <!-- Pipeline steps -->
      <section class="mt-10">
        <h2 class="font-display">ארבעת השלבים</h2>
        <ol class="list-none p-0 m-0 space-y-3 mt-4">
          <li
            v-for="(step, i) in pipeline"
            :key="i"
            class="card p-5 flex gap-4"
          >
            <div class="flex-none w-10 h-10 rounded-gov-pill bg-brand-50 text-brand-700 font-display grid place-items-center">
              {{ i + 1 }}
            </div>
            <div class="flex-1">
              <h3 class="font-display text-ink m-0 mb-1">{{ step.title }}</h3>
              <p class="text-ink/85 leading-relaxed m-0">{{ step.body }}</p>
            </div>
          </li>
        </ol>
      </section>

      <!-- Trust principles -->
      <section class="mt-12">
        <h2 class="font-display">למה אפשר לסמוך?</h2>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">
          <div v-for="(t, i) in trust" :key="i" class="card p-5">
            <h3 class="font-display text-ink m-0 mb-2 text-base">
              <img src="/icons/circle-check.svg" alt="" class="inline w-4 h-4 ms-1 align-middle opacity-80" />
              {{ t.title }}
            </h3>
            <p class="text-ink/80 leading-relaxed m-0 text-sm">{{ t.body }}</p>
          </div>
        </div>
      </section>

      <!-- Limits -->
      <section class="mt-12">
        <h2 class="font-display">מגבלות שכדאי להכיר</h2>
        <ul class="space-y-2 text-ink/85 leading-relaxed">
          <li>• מאגרים חסרי מבנה ברור (למשל קובץ PDF סרוק) יקבלו דף מינימלי.</li>
          <li>• ייתכן עיכוב בין עדכון המאגר במקור הממשלתי לבין הופעתו באתר.</li>
          <li>• התוכן נכתב על ידי AI — לשימוש פורמלי (מחקר, עיתונות, רגולציה) מומלץ להצליב עם המקור הרשמי.</li>
        </ul>
      </section>

      <div class="mt-12 flex flex-wrap gap-3">
        <NuxtLink to="/datasets/" class="btn-primary">
          <img src="/icons/database.svg" alt="" class="w-4 h-4 invert opacity-90" />
          גלה מאגרים
        </NuxtLink>
        <NuxtLink to="/faq/" class="btn-ghost">
          שאלות נפוצות
        </NuxtLink>
      </div>
    </article>
  </div>
</template>
