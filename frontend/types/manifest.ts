// Mirror of services/page_builder/schema.py::ManifestEntry / Manifest.

export type DatasetKind = 'map' | 'timeseries' | 'registry' | 'rankings' | 'misc'

export interface ResourceEntry {
  url: string
  format: string
  name?: string
  size_bytes?: number
  description?: string
}

export interface ManifestEntry {
  id: string
  slug: string
  title: string
  organization?: string
  organization_slug?: string
  summary_he?: string
  tags_he: string[]
  primary_resource_id?: string
  formats: string[]
  metadata_modified?: string
  license?: string
  record_count?: number
  resources?: ResourceEntry[]
  dataset_kind?: DatasetKind
  related_ids: string[]
  embedding?: number[]
  version: number
}

export interface Manifest {
  version: number
  generated_at: string
  datasets: ManifestEntry[]
}
