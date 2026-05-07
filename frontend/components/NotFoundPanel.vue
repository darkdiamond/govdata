<script setup lang="ts">
const props = withDefaults(defineProps<{
  statusCode?: number | string
  heading?: string
  message?: string
}>(), {
  statusCode: 404,
})

const code = computed(() => String(props.statusCode))
const isNotFound = computed(() => code.value === '404')

const headingText = computed(
  () => props.heading ?? (isNotFound.value ? 'העמוד לא נמצא' : 'אירעה שגיאה'),
)

const messageText = computed(
  () => props.message ?? (
    isNotFound.value
      ? 'ייתכן שהקישור שגוי, שהעמוד הוסר או שעוד לא נוצר. ננסה משהו אחר?'
      : 'משהו השתבש בצד שלנו. אפשר לנסות לרענן או לחזור לדף הבית.'
  ),
)
</script>

<template>
  <div class="max-w-gov mx-auto px-4 py-16 sm:py-24">
    <article class="max-w-2xl mx-auto text-center">
      <div
        class="font-display text-brand leading-none select-none"
        :class="isNotFound ? 'text-[7rem] sm:text-[9rem]' : 'text-[5rem] sm:text-[6rem]'"
        aria-hidden="true"
      >
        {{ code }}
      </div>

      <h1 class="font-display mt-2">{{ headingText }}</h1>

      <p class="text-ink/80 text-lg leading-relaxed mt-4">
        {{ messageText }}
      </p>

      <div class="flex flex-wrap justify-center gap-3 mt-8">
        <NuxtLink to="/" class="btn-primary">
          חזרה לדף הבית
        </NuxtLink>
        <NuxtLink to="/datasets/" class="btn-ghost">
          לכל המאגרים
        </NuxtLink>
      </div>

      <p class="text-subtle text-xs mt-8 m-0">
        שגיאה {{ code }}
      </p>
    </article>
  </div>
</template>
