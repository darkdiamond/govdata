<script setup lang="ts">
const faqs = [
  {
    q: 'האם govil.ai הוא אתר ממשלתי רשמי?',
    a: 'לא. זהו פרויקט עצמאי. המאגרים עצמם רכוש המדינה ומופקים מהאתרים הממשלתיים הרשמיים, אך האתר הזה, התקצירים, ודפי הנחיתה מופעלים באופן פרטי. אנחנו מציגים את המידע הציבורי בצורה נגישה יותר — לא מחליפים את המקור.',
  },
  {
    q: 'האם התוכן שנוצר בבינה מלאכותית מדויק?',
    a: 'התקצירים והתובנות מעוגנים במאגרים עצמם ובמקורות ציבוריים שהסוכן שלף בזמן הכתיבה. אם מצאתם אי-דיוק, דווחו לנו ונעדכן. לשימוש פורמלי (מחקר, עיתונות, רגולציה) — תמיד הצליבו מול המקור הרשמי שמופיע בכל דף.',
  },
  {
    q: 'כל כמה זמן מתעדכנים הדפים?',
    a: 'האתר עוקב באופן רציף אחר עדכונים במקור. ברגע שמאגר מתעדכן, הסוכן כותב מחדש את הדף המתאים — בדרך כלל תוך מספר דקות עד שעות. אין צורך לרענן ידנית.',
  },
  {
    q: 'איך בדיוק ה-AI יוצר את הדפים?',
    a: 'סוכן AI אוטונומי קורא את המאגר, מחפש ברשת הקשר רגולטורי ונושאי, ומחליט איזו תצוגה תתאים — מפה, גרף זמן, רשימה או טבלה. הוא כותב את התקציר והתובנות ללא התערבות אנושית, ועובד באותה צורה על אלפי מאגרים.',
  },
  {
    q: 'האם אתם אוספים נתונים עליי?',
    a: 'האתר עצמו סטטי — אין מערכת חברים, אין רישום, אין טפסים שאתם נדרשים למלא כדי לקרוא. כדי להבין דפוסי שימוש כלליים אנו מפעילים Google Analytics, וכדי לממן את התפעול אנו מציגים פרסומות דרך Google AdSense — שני השירותים מציבים cookies בדפדפן. הפירוט המלא, כולל הוראות ביטול הסכמה, מופיע במדיניות הפרטיות בכתובת /privacy/.',
  },
  {
    q: 'איך מציעים מאגר חדש או מדווחים על שגיאה?',
    a: 'שלחו לנו דוא״ל לכתובת hello@govil.ai עם קישור למאגר ותיאור קצר של הבעיה או ההצעה. אנחנו עונים תוך ימים ספורים.',
  },
  {
    q: 'האם אפשר לשתף ולהטמיע את הדפים?',
    a: 'כן, וזו בדיוק המטרה. כל דף מעוצב לשיתוף — קישור בודד מספיק כדי להעביר את המידע לעמית, עיתונאי או קרוב משפחה שלא היו פותחים קובץ CSV בחיים.',
  },
]

useSeo({
  title: 'שאלות ותשובות',
  description: 'שאלות נפוצות על govil.ai — האם זה אתר רשמי, עד כמה התוכן שנוצר ב-AI מדויק, מתי הדפים מתעדכנים, ואיך מדווחים על שגיאה.',
  path: '/faq/',
  keywords: ['FAQ', 'שאלות נפוצות', 'AI מדויק', 'איך לדווח שגיאה'],
  breadcrumbs: [
    { name: 'ראשי', url: 'https://govil.ai/' },
    { name: 'שאלות ותשובות', url: 'https://govil.ai/faq/' },
  ],
  extraJsonLd: {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: faqs.map((f) => ({
      '@type': 'Question',
      name: f.q,
      acceptedAnswer: { '@type': 'Answer', text: f.a },
    })),
  },
})
</script>

<template>
  <div class="max-w-gov mx-auto px-4 py-8">
    <div class="text-xs text-subtle mb-2">
      <NuxtLink to="/">ראשי</NuxtLink> › שאלות ותשובות
    </div>

    <article class="max-w-3xl">
      <h1 class="font-display">שאלות ותשובות</h1>
      <p class="mt-4 text-ink/80 leading-relaxed">
        כל מה שחשוב לדעת על govil.ai, הבינה המלאכותית שמפעילה אותו, ומה ההבדל בינו לבין האתר הממשלתי הרשמי.
      </p>

      <div class="mt-8 space-y-3">
        <details
          v-for="(f, i) in faqs"
          :key="i"
          class="card p-0 group"
        >
          <summary class="list-none cursor-pointer p-5 flex items-center justify-between gap-4 font-display text-ink hover:bg-brand-50/50 rounded-gov">
            <span>{{ f.q }}</span>
            <span aria-hidden="true" class="text-brand-700 text-xl transition-transform group-open:rotate-45 select-none">+</span>
          </summary>
          <div class="px-5 pb-5 pt-0 text-ink/85 leading-relaxed border-t border-rule">
            <p class="m-0 pt-4">{{ f.a }}</p>
          </div>
        </details>
      </div>

      <div class="mt-10 card p-5 bg-brand-50/50 border-brand-100">
        <div class="font-display text-ink mb-1">לא מצאתם תשובה?</div>
        <p class="text-sm text-ink/85 leading-relaxed m-0">
          כתבו לנו ב-<a href="mailto:hello@govil.ai" class="text-brand-700 underline">hello@govil.ai</a>.
        </p>
      </div>
    </article>
  </div>
</template>
