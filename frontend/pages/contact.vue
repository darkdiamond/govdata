<script setup lang="ts">
useSeo({
  title: 'יצירת קשר עם צוות govil.ai',
  description: 'יצירת קשר עם צוות govil.ai — שאלות, פידבק, דיווח על באגים ובקשות למאגרים נוספים.',
  path: '/contact/',
  keywords: ['יצירת קשר', 'פידבק', 'דיווח באגים', 'govil.ai'],
  breadcrumbs: [
    { name: 'ראשי', url: 'https://govil.ai/' },
    { name: 'יצירת קשר', url: 'https://govil.ai/contact/' },
  ],
})

type Status = 'idle' | 'sending' | 'sent' | 'error'
const status = ref<Status>('idle')
const errorMsg = ref('')

async function onSubmit(e: Event) {
  const form = e.target as HTMLFormElement
  status.value = 'sending'
  errorMsg.value = ''
  try {
    const res = await fetch(form.action, {
      method: 'POST',
      headers: { Accept: 'application/json' },
      body: new FormData(form),
    })
    if (res.ok) {
      status.value = 'sent'
      form.reset()
      return
    }
    const data = await res.json().catch(() => null) as { errors?: { message?: string }[] } | null
    errorMsg.value = data?.errors?.[0]?.message || 'שליחה נכשלה. נסו שוב או שלחו לנו אימייל ל-hello@govil.ai.'
    status.value = 'error'
  } catch {
    errorMsg.value = 'בעיית חיבור. נסו שוב או שלחו לנו אימייל ל-hello@govil.ai.'
    status.value = 'error'
  }
}
</script>

<template>
  <div class="max-w-gov mx-auto px-4 py-8">
    <div class="text-xs text-subtle mb-2">
      <NuxtLink to="/">ראשי</NuxtLink> › יצירת קשר
    </div>

    <article class="max-w-3xl">
      <h1 class="font-display">יצירת קשר</h1>
      <p class="mt-4 text-lg text-ink/80 leading-relaxed">
        שאלה, רעיון, דיווח על באג, או בקשה למאגר חסר — נשמח לשמוע.
        רק דוא"ל והודעה הם שדות חובה.
      </p>

      <div
        v-if="status === 'sent'"
        class="card p-6 mt-6 border-r-4 border-r-ok"
        role="status"
        aria-live="polite"
      >
        <h2 class="font-display mt-0 mb-2">תודה!</h2>
        <p class="text-ink/85 m-0 leading-relaxed">
          ההודעה התקבלה. נחזור אליכם בהקדם האפשרי.
        </p>
      </div>

      <form
        v-else
        action="https://formspree.io/f/xojrvowr"
        method="POST"
        class="card p-6 mt-6 space-y-4"
        novalidate
        @submit.prevent="onSubmit"
      >
        <input type="hidden" name="_subject" value="פנייה חדשה מ-govil.ai" />
        <input
          type="text"
          name="_gotcha"
          tabindex="-1"
          autocomplete="off"
          aria-hidden="true"
          class="hidden"
        />

        <div>
          <label for="name" class="block text-sm text-ink/85 mb-1">שם <span class="text-subtle">(אופציונלי)</span></label>
          <input
            id="name"
            name="name"
            type="text"
            autocomplete="name"
            class="w-full border border-rule rounded-gov px-3 py-2 bg-white focus:outline-none focus:border-brand focus:ring-1 focus:ring-brand"
          />
        </div>

        <div>
          <label for="email" class="block text-sm text-ink/85 mb-1">דוא"ל <span class="text-danger" aria-hidden="true">*</span></label>
          <input
            id="email"
            name="email"
            type="email"
            required
            autocomplete="email"
            class="w-full border border-rule rounded-gov px-3 py-2 bg-white focus:outline-none focus:border-brand focus:ring-1 focus:ring-brand"
          />
        </div>

        <div>
          <label for="topic" class="block text-sm text-ink/85 mb-1">נושא <span class="text-subtle">(אופציונלי)</span></label>
          <select
            id="topic"
            name="topic"
            class="w-full border border-rule rounded-gov px-3 py-2 bg-white focus:outline-none focus:border-brand focus:ring-1 focus:ring-brand"
          >
            <option value="">בחרו נושא…</option>
            <option>שאלה כללית</option>
            <option>פידבק</option>
            <option>דיווח על באג</option>
            <option>בקשת מאגר</option>
            <option>שיתוף פעולה</option>
            <option>אחר</option>
          </select>
        </div>

        <div>
          <label for="message" class="block text-sm text-ink/85 mb-1">הודעה <span class="text-danger" aria-hidden="true">*</span></label>
          <textarea
            id="message"
            name="message"
            required
            rows="6"
            class="w-full border border-rule rounded-gov px-3 py-2 bg-white resize-y focus:outline-none focus:border-brand focus:ring-1 focus:ring-brand"
          ></textarea>
        </div>

        <p
          v-if="status === 'error'"
          class="text-sm text-danger m-0"
          role="alert"
        >
          {{ errorMsg }}
        </p>

        <div class="flex flex-wrap items-center gap-3 pt-2">
          <button
            type="submit"
            :disabled="status === 'sending'"
            class="btn-primary disabled:opacity-60 disabled:cursor-wait"
          >
            {{ status === 'sending' ? 'שולח…' : 'שליחה' }}
          </button>
          <span class="text-xs text-subtle">
            פרטי הקשר משמשים רק כדי לחזור אליכם.
          </span>
        </div>
      </form>

      <p class="text-sm text-subtle mt-6">
        מעדיפים אימייל ישיר?
        <a href="mailto:hello@govil.ai">hello@govil.ai</a>
      </p>
    </article>
  </div>
</template>
