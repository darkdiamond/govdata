// Loads Google AdSense (Auto Ads) AFTER Vue finishes hydrating.
//
// Auto Ads has no markup in our pages — the script itself scans the DOM and
// inserts <ins class="adsbygoogle"> slots wherever it decides. When it was a
// plain head script it raced hydration: on production (where ads actually
// fill) the DOM Vue was hydrating against no longer matched the server HTML,
// logging "Hydration completed but contains mismatches" on dataset pages and
// risking a re-render of the agent body. Locally the ad request 403s, which
// is why the mismatch never reproduced outside prod.
//
// `app:mounted` fires once per page load after hydration completes; the
// AdSense account meta tag stays in head (nuxt.config.ts) so site
// verification is unaffected.
export default defineNuxtPlugin((nuxtApp) => {
  const adsenseId = useRuntimeConfig().public.adsenseId
  if (!adsenseId) return
  nuxtApp.hook('app:mounted', () => {
    const s = document.createElement('script')
    s.async = true
    s.crossOrigin = 'anonymous'
    s.src = `https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${adsenseId}`
    document.head.appendChild(s)
  })
})
