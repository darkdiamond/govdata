<script setup lang="ts">
useSeo({
  title: 'מידע ממשלתי פתוח, מובן ומקושר — על ידי AI',
  description: 'כל מאגר שפרסמה ממשלת ישראל נסרק על ידי סוכן בינה מלאכותית מתקדם, שמנתח אותו לעומק ומפיק תקציר, ויזואליזציות, גרפים, תובנות וקישורים — בלי CSV ובלי ידע טכני.',
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
