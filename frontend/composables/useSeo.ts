// Shared SEO helper. Emits title, description, canonical, OG, Twitter,
// and a small JSON-LD block describing the site. Keywords seeded with the
// AI/agentic terms the site ranks on (Hebrew + English).

const SITE_URL = 'https://gov-il.ai'
const SITE_NAME = 'gov-il.ai'
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

export interface SeoInput {
  title: string
  description: string
  path: string
  ogImage?: string
  keywords?: string[]
}

export function useSeo(input: SeoInput) {
  const title = input.title.includes(SITE_NAME) ? input.title : `${input.title} — ${SITE_NAME}`
  const url = `${SITE_URL}${input.path}`
  const image = input.ogImage ? `${SITE_URL}${input.ogImage}` : `${SITE_URL}${DEFAULT_OG}`
  const keywords = [...BASE_KEYWORDS, ...(input.keywords ?? [])].join(', ')

  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    name: SITE_NAME,
    url: SITE_URL,
    inLanguage: 'he-IL',
    description: input.description,
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
    script: [
      {
        type: 'application/ld+json',
        innerHTML: JSON.stringify(jsonLd),
      },
    ],
  })
}
