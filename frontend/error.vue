<script setup lang="ts">
import type { NuxtError } from '#app'

const props = defineProps<{ error: NuxtError }>()

const code = computed(() => props.error?.statusCode ?? 500)

useHead({
  title: computed(() => `${code.value === 404 ? 'העמוד לא נמצא' : 'אירעה שגיאה'} — govil.ai`),
  meta: [
    { name: 'description', content: 'העמוד שחיפשתם לא נמצא ב-govil.ai. חזרו לדף הבית או עיינו בכל המאגרים הממשלתיים.' },
    { name: 'robots', content: 'noindex' },
  ],
})
</script>

<template>
  <NuxtLayout name="default">
    <NotFoundPanel :status-code="code" />
  </NuxtLayout>
</template>
