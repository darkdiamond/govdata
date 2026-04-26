// Normalizes agent-authored content.html before it hits v-html in
// pages/datasets/[id].vue. Single ingress point so every dataset page
// gets the same defenses regardless of which day the agent ran.
//
// Three transforms:
//   1. e.data.gov.il (IAP-gated) -> data.gov.il (public CKAN host).
//   2. Backslash-escaped script-end tag -> real script-end tag. HTML5 only
//      recognizes the unescaped form; a single backslash form inside an
//      external script tag silently swallows everything until the next
//      real end tag, hiding the init code from the parser.
//   3. Drop duplicate viz-lib script and stylesheet tags. The page shell
//      already preloads Leaflet + MarkerCluster + ECharts via
//      useHead(DATASET_LIB_TAGS) from /lib/ on the same origin; the
//      agent occasionally re-includes the same libs from public CDNs
//      with stale SRI hashes, which fails integrity and noises up the
//      console.

const ESCAPED_SCRIPT_END = /<\\\/script>/g
const IAP_HOST = /https:\/\/e\.data\.gov\.il/g

const LIB_SCRIPT_RE = new RegExp(
  '<script\\b[^>]*\\bsrc=["\\\'][^"\\\']*' +
    '(?:leaflet[^"\\\']*\\.js|MarkerCluster[^"\\\']*\\.js|echarts[^"\\\']*\\.js)' +
    '["\\\'][^>]*>\\s*<\\\\?\\/script>',
  'gi',
)

const LIB_STYLE_RE = new RegExp(
  '<link\\b[^>]*\\bhref=["\\\'][^"\\\']*' +
    '(?:leaflet[^"\\\']*\\.css|MarkerCluster[^"\\\']*\\.css)' +
    '["\\\'][^>]*\\/?>',
  'gi',
)

export function normalizeAgentBody(raw: string): string {
  return raw
    .replace(IAP_HOST, 'https://data.gov.il')
    .replace(ESCAPED_SCRIPT_END, '</' + 'script>')
    .replace(LIB_SCRIPT_RE, '')
    .replace(LIB_STYLE_RE, '')
}
