// Copy curated viz libs from node_modules into public/lib/ so dataset
// pages can load them as same-origin assets (no public CDN, no SRI). The
// list mirrors utils/dataset-libs.ts (which references the public/lib/
// URLs from useHead) — keep them in sync. Wired into npm's predev /
// prebuild / pregenerate lifecycle scripts so it runs every build.
import { copyFile, mkdir, readdir, stat } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const root = resolve(here, '..')

const FILES = [
  ['leaflet/dist/leaflet.js', 'leaflet.js'],
  ['leaflet/dist/leaflet.css', 'leaflet.css'],
  ['leaflet.markercluster/dist/leaflet.markercluster.js', 'leaflet.markercluster.js'],
  ['leaflet.markercluster/dist/MarkerCluster.css', 'MarkerCluster.css'],
  ['leaflet.markercluster/dist/MarkerCluster.Default.css', 'MarkerCluster.Default.css'],
  ['echarts/dist/echarts.min.js', 'echarts.min.js'],
]

// Leaflet's CSS references images at `images/marker-icon.png` etc. relative to
// the stylesheet — copy the whole dir so default markers work.
const IMAGE_DIRS = [
  ['leaflet/dist/images', 'images'],
]

async function copyDir(srcDir, dstDir) {
  await mkdir(dstDir, { recursive: true })
  for (const name of await readdir(srcDir)) {
    const src = resolve(srcDir, name)
    const dst = resolve(dstDir, name)
    const st = await stat(src)
    if (st.isDirectory()) await copyDir(src, dst)
    else await copyFile(src, dst)
  }
}

const libDir = resolve(root, 'public/lib')
await mkdir(libDir, { recursive: true })

for (const [from, to] of FILES) {
  const src = resolve(root, 'node_modules', from)
  const dst = resolve(libDir, to)
  await copyFile(src, dst)
  console.log(`  ${from} -> public/lib/${to}`)
}

for (const [from, to] of IMAGE_DIRS) {
  await copyDir(resolve(root, 'node_modules', from), resolve(libDir, to))
  console.log(`  ${from}/* -> public/lib/${to}/`)
}
