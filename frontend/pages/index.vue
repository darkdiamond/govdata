<script setup lang="ts">
import { buildInsightPool } from '~/utils/insights'

useSeo({
  title: 'מאגרי מידע ממשלתיים — מוסבר, מחובר ומובן ע״י AI · govil.ai',
  description: 'סוכן AI סורק כל מאגר מידע ממשלתי שמתפרסם, מסביר את הנתונים בעברית ומנגיש אותם בעמוד אחד עם ויזואליזציות אינטראקטיביות. בלי הורדות, בלי Excel.',
  path: '/',
  keywords: [
    'מאגרי מידע ממשלתיים',
    'מידע ממשלתי פתוח',
    'סוכן AI ממשלתי',
    'AI ישראל',
    'open data Israel',
  ],
})

const manifest = useManifest()
const insightPool = computed(() => buildInsightPool(manifest.value?.datasets ?? []))
</script>

<template>
  <div class="max-w-gov mx-auto px-4 py-8 space-y-16">
    <Hero />
    <InsightCarousel :pool="insightPool" />
    <WhatYouGet />
    <HowItWorks />
    <BrowseByMinistry />
    <BrowseByKind />
    <LatestDatasets />
    <CallToAction />
  </div>
</template>
