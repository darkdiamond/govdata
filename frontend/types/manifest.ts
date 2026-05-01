// Mirror of services/page_builder/schema.py.
//
// Per-dataset structured data is split across two files:
//   datasets/<id>/data.json       → DatasetMeta (scanner-derived facts)
//   datasets/<id>/agent_data.json → AgentData   (agent-derived judgments)
//
// frontend/pages/datasets/[id].vue reads both at SSG time and merges
// them into a `ManifestEntry`-shaped object that all downstream
// rendering consumes. The aggregated data/manifest.json published from
// Firestore already contains the merged shape, so the home + category
// pages need only ManifestEntry.

export type DatasetKind = 'map' | 'timeseries' | 'registry' | 'rankings' | 'misc'

export interface ResourceEntry {
  url: string
  format: string
  name?: string
  size_bytes?: number
  description?: string
}

/** Scanner-derived metadata. Single source of truth: Firestore `sources/<id>` */
export interface DatasetMeta {
  id: string
  slug: string
  title: string
  organization?: string
  organization_slug?: string
  tags_he: string[]
  primary_resource_id?: string
  formats: string[]
  metadata_modified?: string
  license?: string
  record_count?: number
  resources?: ResourceEntry[]
  last_analyzed_at?: string
  version: number
}

/** Agent-derived judgments. Single source of truth: Firestore `sources/<id>.agent_data` */
export interface AgentData {
  summary_he: string
  dataset_kind: DatasetKind
  related_ids?: string[]
  version: number
  // `extra='allow'` on the pydantic side — future fields land here.
  [key: string]: unknown
}

/** Merged view consumed by every rendering site (home, category pages, dataset page). */
export interface ManifestEntry {
  // DatasetMeta fields
  id: string
  slug: string
  title: string
  organization?: string
  organization_slug?: string
  tags_he: string[]
  primary_resource_id?: string
  formats: string[]
  metadata_modified?: string
  license?: string
  record_count?: number
  resources?: ResourceEntry[]
  last_analyzed_at?: string

  // AgentData fields (optional — a scanned-but-never-analyzed source has none)
  summary_he?: string
  dataset_kind?: DatasetKind

  // Publisher-computed
  related_ids: string[]
  embedding?: number[]
  version: number
}

export interface Manifest {
  version: number
  generated_at: string
  datasets: ManifestEntry[]
}
