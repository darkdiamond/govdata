<script setup lang="ts">
useSeo({
  title: 'אודות',
  description: 'gov-il.ai מנגיש את כל המאגרים הממשלתיים לכל אחד. AI כותב עבור כל מאגר עמוד הסבר בעברית — תקציר, ויזואליזציות ותובנות — בלי CSV ובלי ידע טכני.',
  path: '/about/',
  keywords: ['על הפרויקט', 'נגישות מידע ממשלתי', 'AI לציבור'],
})
</script>

<template>
  <div class="max-w-gov mx-auto px-4 py-8">
    <div class="text-xs text-subtle mb-2">
      <NuxtLink to="/">ראשי</NuxtLink> › אודות
    </div>

    <article class="max-w-3xl">
      <h1 class="font-display">אודות gov-il.ai</h1>
      <p class="mt-4 text-lg text-ink/80 leading-relaxed">
        gov-il.ai הוא אתר ציבורי שמנגיש את המידע הממשלתי הפתוח של ישראל לכל אחד —
        ולא רק לאנשי מקצוע שיודעים לעבוד עם קובצי נתונים.
      </p>

      <h2 class="font-display mt-10">הבעיה שאנחנו פותרים</h2>
      <p class="text-ink/85 leading-relaxed">
        הממשלה מפרסמת אלפי מאגרי מידע. הבעיה: רבים מהם מגיעים כקובצי נתונים גולמיים —
        עמודות באנגלית, תאריכים בפורמטים משונים, ללא הקשר ובלי הסבר. כתוצאה מכך, המידע
        <strong>זמין</strong> אבל לא <strong>נגיש</strong> — רק מי שיודע להשתמש ב-Excel או
        לכתוב קוד יכול להפיק ממנו תועלת.
      </p>
      <p class="text-ink/85 leading-relaxed">
        <strong>gov-il.ai סוגר את הפער הזה.</strong> סוכני AI לוקחים כל מאגר, קוראים אותו,
        מסכמים אותו בעברית, ממחישים אותו בוויזואליזציות מתאימות, ומציפים את התובנות
        המשמעותיות. התוצאה: עמוד אחד בעברית לכל מאגר — מוכן לקריאה, לשיתוף ולהבנה.
      </p>

      <h2 class="font-display mt-10">למי זה מתאים?</h2>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">
        <div class="card p-5">
          <h3 class="font-display text-ink m-0 mb-1 text-base">לאזרחים</h3>
          <p class="text-sm text-ink/80 m-0 leading-relaxed">
            להבין מה הממשלה יודעת על הנושאים שחשובים לכם — בלי צורך בכלים מקצועיים.
          </p>
        </div>
        <div class="card p-5">
          <h3 class="font-display text-ink m-0 mb-1 text-base">לעיתונאים</h3>
          <p class="text-sm text-ink/80 m-0 leading-relaxed">
            תובנות מוכנות לפרסום, עם קישור ישיר למקור הרשמי — להצלבה ולאימות.
          </p>
        </div>
        <div class="card p-5">
          <h3 class="font-display text-ink m-0 mb-1 text-base">לחוקרים וסטודנטים</h3>
          <p class="text-sm text-ink/80 m-0 leading-relaxed">
            נקודת פתיחה מהירה לכל מאגר — תקציר, מבנה הנתונים, ומאגרים קשורים.
          </p>
        </div>
        <div class="card p-5">
          <h3 class="font-display text-ink m-0 mb-1 text-base">לכל אחד שרוצה לשתף</h3>
          <p class="text-sm text-ink/80 m-0 leading-relaxed">
            לינק לעמוד אחד בעברית שוות הרבה יותר מקישור לקובץ CSV. קל להבין, קל לשתף.
          </p>
        </div>
      </div>

      <h2 class="font-display mt-10">מה אנחנו <em>לא</em></h2>
      <div class="card p-5 bg-brand-50/50 border-brand-100">
        <p class="text-ink/85 leading-relaxed m-0">
          <strong>gov-il.ai אינו אתר ממשלתי רשמי.</strong> הפרויקט מופעל באופן עצמאי.
          המאגרים עצמם רכוש המדינה ומופקים מהאתרים הממשלתיים הרשמיים. התקצירים,
          התובנות והוויזואליזציות נכתבו אוטומטית על ידי AI — מעוגנים במקור, אך עשויים להכיל
          אי-דיוקים. לשימוש פורמלי — תמיד הצליבו מול המקור הרשמי.
        </p>
      </div>

      <h2 class="font-display mt-10">יצירת קשר</h2>
      <p class="text-ink/85 leading-relaxed">
        מצאתם שגיאה? רוצים להציע מאגר? יש לכם רעיון לשיפור?
      </p>
      <div class="flex flex-wrap gap-3 mt-4">
        <a href="mailto:hello@gov-il.ai" class="btn-primary">
          hello@gov-il.ai
        </a>
      </div>

      <h2 class="font-display mt-10">תודות</h2>
      <p class="text-ink/85 leading-relaxed">
        תודה למשרדי הממשלה, הרשויות והאגפים שמפרסמים את הנתונים שלהם בגלוי — בלעדיהם
        הפרויקט הזה לא היה קיים.
      </p>
    </article>
  </div>
</template>
