// Ping IndexNow (Bing/Yandex/Seznam/Naver) with every URL in the generated
// sitemap, so new dataset pages get crawled within hours instead of weeks.
// Runs as a post-deploy step in .github/workflows/publish.yml; never fails
// the deploy. The key file lives at frontend/public/<KEY>.txt (same KEY) —
// IndexNow verifies ownership by fetching it from the live site.
import { readFileSync } from 'node:fs'

const KEY = 'd6ede06d967d8c5ae326761d20ad54f3'
const HOST = 'govil.ai'

let urls = []
try {
  const sitemap = readFileSync(new URL('../.output/public/sitemap.xml', import.meta.url), 'utf-8')
  urls = [...sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1])
} catch (err) {
  console.warn('[indexnow] no sitemap found, skipping:', err.message)
  process.exit(0)
}

if (urls.length === 0) {
  console.warn('[indexnow] sitemap had no URLs, skipping')
  process.exit(0)
}

try {
  const res = await fetch('https://api.indexnow.org/indexnow', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
    body: JSON.stringify({
      host: HOST,
      key: KEY,
      keyLocation: `https://${HOST}/${KEY}.txt`,
      urlList: urls.slice(0, 10000), // protocol cap per request
    }),
  })
  console.log(`[indexnow] pinged ${urls.length} URLs -> HTTP ${res.status}`)
} catch (err) {
  console.warn('[indexnow] ping failed (non-fatal):', err.message)
}
