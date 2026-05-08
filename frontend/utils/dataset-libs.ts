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
    // window.echarts / window.GovExplorer exist before the body's inline
    // init runs during initial parse. On SPA nav useHead appends the same
    // tags to <head>; executeBodyScripts() in pages/datasets/[id].vue
    // waits on globals before re-running body scripts.
    { src: '/lib/leaflet.js' },
    { src: '/lib/leaflet.markercluster.js' },
    { src: '/lib/echarts.min.js' },
    // Hand-written browser libs (sourced from frontend/scripts/,
    // copied into public/lib/ by scripts/copy-libs.mjs):
    //   gov-echarts.js   → window.GOVIL_PALETTE + window.GovEcharts.{base,option}
    //                      so per-page <script> blocks don't redefine
    //                      the palette + RTL/Rubik base config.
    //   gov-explorer.js  → window.GovExplorer.create for live
    //                      datastore_search-backed search + pagination.
    //   gov-map.js       → window.GovMap.create for paginated,
    //                      clustered Leaflet maps over CKAN.
    { src: '/lib/gov-echarts.js' },
    { src: '/lib/gov-explorer.js' },
    { src: '/lib/gov-map.js' },
  ],
}
