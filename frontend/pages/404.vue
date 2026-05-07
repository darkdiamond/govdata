<script setup lang="ts">
useSeo({
  title: 'העמוד לא נמצא',
  description: 'העמוד שחיפשתם לא נמצא ב-govil.ai. חזרו לדף הבית או עיינו בכל המאגרים הממשלתיים.',
  path: '/404/',
})

useHead({
  meta: [{ name: 'robots', content: 'noindex' }],
})
</script>

<template>
  <NotFoundPanel :status-code="404" />
</template>
