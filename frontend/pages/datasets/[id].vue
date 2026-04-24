<script setup lang="ts">
import { useManifest } from '~/composables/useManifest'
import type { ManifestEntry } from '~/types/manifest'

const route = useRoute()
const id = String(route.params.id)

const { data } = await useAsyncData(`dataset-${id}`, async () => {
  const fs = await import('node:fs/promises')
  const path = await import('node:path')
  const dir = path.resolve(process.cwd(), 'public/datasets', id)

  const rawBody = await fs.readFile(path.join(dir, 'content.html'), 'utf-8')
  const body = rawBody.replace(/https:\/\/e\.data\.gov\.il/g, 'https://data.gov.il')

  const entry = JSON.parse(
    await fs.readFile(path.join(dir, 'data.json'), 'utf-8'),
  ) as ManifestEntry

  return { entry, body }
})

if (!data.value) {
  throw createError({ statusCode: 404, statusMessage: 'Dataset not found', fatal: true })
}

const entry = computed(() => data.value!.entry)
const body = computed(() => data.value!.body)

const manifest = useManifest()
const related = computed<ManifestEntry[]>(() => {
  const ids = entry.value.related_ids ?? []
  const byId = new Map((manifest.value?.datasets ?? []).map((d) => [d.id, d]))
  return ids
    .map((rid) => byId.get(rid))
    .filter((d): d is ManifestEntry => Boolean(d))
    .slice(0, 5)
})

const KIND_LABELS_HE: Record<string, string> = {
  map: 'גיאוגרפי',
  timeseries: 'סדרת זמן',
  registry: 'רשימת ישויות',
  rankings: 'דירוגים',
  misc: 'אחר',
}
const kindLabel = computed(() =>
  entry.value.dataset_kind ? KIND_LABELS_HE[entry.value.dataset_kind] ?? 'אחר' : '',
)

useSeo({
  title: entry.value.title,
  description: (entry.value.summary_he ?? entry.value.title).slice(0, 160),
  path: `/datasets/${entry.value.id}/`,
})
</script>

<template>
  <div>
    <nav aria-label="breadcrumb" class="border-b border-rule bg-white">
      <div class="max-w-gov mx-auto px-4 py-2 text-xs text-subtle">
        <NuxtLink to="/">ראשי</NuxtLink>
        <template v-if="entry.organization && entry.organization_slug">
          <span class="mx-1">›</span>
          <NuxtLink :to="`/ministries/${entry.organization_slug}/`">{{ entry.organization }}</NuxtLink>
        </template>
        <span class="mx-1">›</span>
        <span>{{ entry.title }}</span>
      </div>
    </nav>

    <div class="max-w-gov mx-auto px-4 py-8 grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-8">
      <article class="dataset-body" v-html="body" />

      <aside class="space-y-4">
        <section v-if="related.length" class="card p-4">
          <h3 class="m-0 mb-3 text-sm text-subtle font-display">מאגרים קשורים</h3>
          <ul class="list-none m-0 p-0 space-y-2">
            <li v-for="r in related" :key="r.id">
              <NuxtLink
                :to="`/datasets/${r.id}/`"
                class="block card-hover p-2 rounded-gov-md hover:bg-brand-50 no-underline hover:no-underline"
              >
                <div class="text-sm font-medium text-ink">{{ r.title }}</div>
                <div v-if="r.organization" class="text-xs text-subtle mt-0.5">{{ r.organization }}</div>
                <div v-if="r.summary_he" class="text-xs text-subtle mt-1 line-clamp-2">{{ r.summary_he }}</div>
              </NuxtLink>
            </li>
          </ul>
        </section>

        <section v-if="entry.tags_he?.length" class="card p-4">
          <h3 class="m-0 mb-2 text-sm text-subtle font-display">תגיות</h3>
          <div class="flex flex-wrap gap-1">
            <NuxtLink
              v-for="t in entry.tags_he"
              :key="t"
              :to="`/tags/${encodeURIComponent(t)}/`"
              class="tag-chip hover:bg-brand-100"
            >{{ t }}</NuxtLink>
          </div>
        </section>

        <section v-if="entry.dataset_kind" class="card p-4 text-xs text-subtle">
          סוג מאגר:
          <NuxtLink :to="`/kinds/${entry.dataset_kind}/`" class="badge hover:bg-brand-50">{{ kindLabel }}</NuxtLink>
        </section>
      </aside>
    </div>
  </div>
</template>
