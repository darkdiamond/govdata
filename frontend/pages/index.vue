<script setup lang="ts">
useSeo({
  title: 'מידע ממשלתי פתוח, מובן ומקושר — על ידי AI',
  description: 'gov-il.ai מנגיש את כל המאגרים הממשלתיים בעברית: תקצירים, ויזואליזציות ותובנות שנכתבות אוטומטית על ידי סוכני AI. בלי להוריד קבצים, בלי ידע טכני.',
  path: '/',
  keywords: ['מידע ממשלתי פתוח', 'AI ישראל', 'סוכן AI ממשלתי', 'gov-il.ai'],
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
