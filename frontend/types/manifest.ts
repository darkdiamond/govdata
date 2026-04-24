// Mirror of services/page_builder/schema.py::ManifestEntry / Manifest.

export type DatasetKind = 'map' | 'timeseries' | 'registry' | 'rankings' | 'misc'

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
