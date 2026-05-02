<script setup lang="ts">
useSeo({
  title: 'כל מאגר ממשלתי — מוסבר, מחובר, מובן',
  description: 'סוכן בינה מלאכותית סורק כל מאגר ממשלתי שמתפרסם, מנתח את הנתונים, ומנגיש אותם בעמוד אחד — תקציר, ויזואליזציות אינטראקטיביות ותובנות מוכנות לשיתוף. בלי להוריד קבצים, בלי Excel, בלי ידע טכני.',
  path: '/',
  keywords: ['מידע ממשלתי פתוח', 'AI ישראל', 'סוכן AI ממשלתי', 'govil.ai'],
})
</script>

<template>
  <div class="max-w-gov mx-auto px-4 py-8 space-y-16">
    <Hero />
    <WhatYouGet />
    <HowItWorks />
    <BrowseByMinistry />
    <BrowseByKind />
    <LatestDatasets />
    <CallToAction />
  </div>
</template>
