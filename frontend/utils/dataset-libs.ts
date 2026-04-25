// Curated viz libraries pre-loaded in <head> on dataset pages. Files
// come from public/lib/, populated by scripts/copy-libs.mjs (keep the
// list there in sync). Agent-emitted content.html may NOT include
// <script src=> or <link rel=stylesheet> — these tags are the only
// external resources a dataset page loads.
export const DATASET_LIB_TAGS = {
  link: [
    { rel: 'stylesheet', href: '/lib/leaflet.css' },
    { rel: 'stylesheet', href: '/lib/MarkerCluster.css' },
    { rel: 'stylesheet', href: '/lib/MarkerCluster.Default.css' },
  ],
  script: [
    // Order matters: Leaflet -> MarkerCluster (mutates L) -> ECharts.
    // Plain <script> tags (no defer/async): head-blocking so window.L /
    // window.echarts exist before the body's inline init runs during
    // initial parse. On SPA nav useHead appends the same tags to <head>;
    // executeBodyScripts() in pages/datasets/[id].vue waits on globals
    // before re-running body scripts.
    { src: '/lib/leaflet.js' },
    { src: '/lib/leaflet.markercluster.js' },
    { src: '/lib/echarts.min.js' },
  ],
}
