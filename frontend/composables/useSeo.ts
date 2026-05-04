// Shared SEO helper. Emits title, description, canonical, OG, Twitter,
// and JSON-LD blocks (WebSite always; BreadcrumbList + extras when given).
// Keywords seeded with the AI/agentic terms the site ranks on (Hebrew + English).

const SITE_URL = 'https://govil.ai'
const SITE_NAME = 'govil.ai'
const DEFAULT_OG = '/og-default.png'

const BASE_KEYWORDS = [
  'מידע ממשלתי',
  'data.gov.il',
  'בינה מלאכותית',
  'AI',
  'סוכן AI',
  'agentic',
  'אג׳נטי',
  'מאגרי מידע פתוחים',
  'ישראל',
  'open data Israel',
  'government data',
]

export interface BreadcrumbItem {
  name: string
  url: string
}

export interface SeoInput {
  title: string
  description: string
  path: string
  ogImage?: string
  keywords?: string[]
  breadcrumbs?: BreadcrumbItem[]
  extraJsonLd?: object | object[]
}

export function useSeo(input: SeoInput) {
  const title = input.title.includes(SITE_NAME) ? input.title : `${input.title} — ${SITE_NAME}`
  const url = `${SITE_URL}${input.path}`
  const image = input.ogImage ? `${SITE_URL}${input.ogImage}` : `${SITE_URL}${DEFAULT_OG}`
  const keywords = [...BASE_KEYWORDS, ...(input.keywords ?? [])].join(', ')

  const websiteLd = {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    name: SITE_NAME,
    url: SITE_URL,
    inLanguage: 'he-IL',
    description: input.description,
    image: `${SITE_URL}/favicon-192.png`,
  }

  const ldBlocks: object[] = [websiteLd]

  if (input.breadcrumbs && input.breadcrumbs.length > 0) {
    ldBlocks.push({
      '@context': 'https://schema.org',
      '@type': 'BreadcrumbList',
      itemListElement: input.breadcrumbs.map((b, i) => ({
        '@type': 'ListItem',
        position: i + 1,
        name: b.name,
        item: b.url,
      })),
    })
  }

  if (input.extraJsonLd) {
    if (Array.isArray(input.extraJsonLd)) ldBlocks.push(...input.extraJsonLd)
    else ldBlocks.push(input.extraJsonLd)
  }

  useHead({
    title,
    link: [{ rel: 'canonical', href: url }],
    meta: [
      { name: 'description', content: input.description },
      { name: 'keywords', content: keywords },
      { property: 'og:type', content: 'website' },
      { property: 'og:site_name', content: SITE_NAME },
      { property: 'og:title', content: title },
      { property: 'og:description', content: input.description },
      { property: 'og:url', content: url },
      { property: 'og:image', content: image },
      { property: 'og:locale', content: 'he_IL' },
      { name: 'twitter:card', content: 'summary_large_image' },
      { name: 'twitter:title', content: title },
      { name: 'twitter:description', content: input.description },
      { name: 'twitter:image', content: image },
    ],
    script: ldBlocks.map((ld, i) => ({
      key: `ld-${i}`,
      type: 'application/ld+json',
      innerHTML: JSON.stringify(ld),
    })),
  })
}
