# Graph Report - /mnt/d/workdir/govdata  (2026-05-02)

## Corpus Check
- 138 files · ~213,266 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1324 nodes · 3532 edges · 49 communities detected
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 309 edges (avg confidence: 0.61)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_ECharts vendor bundle (chunk 1)|ECharts vendor bundle (chunk 1)]]
- [[_COMMUNITY_ECharts vendor bundle (chunk 2)|ECharts vendor bundle (chunk 2)]]
- [[_COMMUNITY_Page builder main + Cloud Run entry|Page builder main + Cloud Run entry]]
- [[_COMMUNITY_Voyage embeddings + scoring|Voyage embeddings + scoring]]
- [[_COMMUNITY_Leaflet vendor bundle|Leaflet vendor bundle]]
- [[_COMMUNITY_Managed Agent runtime + contracts|Managed Agent runtime + contracts]]
- [[_COMMUNITY_Dataset SSG artifacts (data.json + agent_data + content.html)|Dataset SSG artifacts (data.json + agent_data + content.html)]]
- [[_COMMUNITY_ECharts vendor bundle (chunk 3)|ECharts vendor bundle (chunk 3)]]
- [[_COMMUNITY_ECharts vendor bundle (chunk 4)|ECharts vendor bundle (chunk 4)]]
- [[_COMMUNITY_Build output artifacts (manifest, sitemap)|Build output artifacts (manifest, sitemap)]]
- [[_COMMUNITY_Scanner CKAN domain models|Scanner CKAN domain models]]
- [[_COMMUNITY_Homepage Vue components|Homepage Vue components]]
- [[_COMMUNITY_ECharts vendor bundle (chunk 5)|ECharts vendor bundle (chunk 5)]]
- [[_COMMUNITY_ECharts vendor bundle (chunk 6)|ECharts vendor bundle (chunk 6)]]
- [[_COMMUNITY_Homepage screenshot (home.png)|Homepage screenshot (home.png)]]
- [[_COMMUNITY_Scanner package modules|Scanner package modules]]
- [[_COMMUNITY_Dead Sea dataset screenshot|Dead Sea dataset screenshot]]
- [[_COMMUNITY_Antennas dataset screenshot|Antennas dataset screenshot]]
- [[_COMMUNITY_Hebrew→Latin slug helper|Hebrew→Latin slug helper]]
- [[_COMMUNITY_GovExplorer (deployed copy)|GovExplorer (deployed copy)]]
- [[_COMMUNITY_GovExplorer (source script)|GovExplorer (source script)]]
- [[_COMMUNITY_Scanner datastore_total tests|Scanner datastore_total tests]]
- [[_COMMUNITY_useKindLabels composable|useKindLabels composable]]
- [[_COMMUNITY_Tailwind config (gov.il tokens)|Tailwind config (gov.il tokens)]]
- [[_COMMUNITY_build-sitemap script|build-sitemap script]]
- [[_COMMUNITY_copy-libs script|copy-libs script]]
- [[_COMMUNITY_Backfill + update-agent ops scripts|Backfill + update-agent ops scripts]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 66|Community 66]]
- [[_COMMUNITY_Community 70|Community 70]]
- [[_COMMUNITY_Community 71|Community 71]]
- [[_COMMUNITY_Community 72|Community 72]]
- [[_COMMUNITY_Community 73|Community 73]]
- [[_COMMUNITY_Community 74|Community 74]]
- [[_COMMUNITY_Community 75|Community 75]]
- [[_COMMUNITY_Community 76|Community 76]]
- [[_COMMUNITY_Community 77|Community 77]]
- [[_COMMUNITY_Community 78|Community 78]]
- [[_COMMUNITY_Community 79|Community 79]]
- [[_COMMUNITY_Community 80|Community 80]]
- [[_COMMUNITY_Community 81|Community 81]]
- [[_COMMUNITY_Community 82|Community 82]]
- [[_COMMUNITY_Community 83|Community 83]]
- [[_COMMUNITY_Community 84|Community 84]]
- [[_COMMUNITY_Community 85|Community 85]]
- [[_COMMUNITY_Community 86|Community 86]]
- [[_COMMUNITY_Community 87|Community 87]]
- [[_COMMUNITY_Community 88|Community 88]]

## God Nodes (most connected - your core abstractions)
1. `E()` - 135 edges
2. `T()` - 72 edges
3. `Y()` - 63 edges
4. `U()` - 53 edges
5. `A()` - 51 edges
6. `z()` - 49 edges
7. `FirestoreStateStore` - 43 edges
8. `q()` - 42 edges
9. `Dataset` - 41 edges
10. `X()` - 40 edges

## Surprising Connections (you probably didn't know these)
- `govdata-design SKILL.md` --documents--> `_()`  [EXTRACTED]
  /mnt/d/workdir/govdata/agent/skills/govdata-design/SKILL.md → frontend/public/lib/leaflet.js
- `Dataset: 01aeaf5c-59a2-4ddc-a616-31b85621bfe2 (חברות בפרוק מרצון בהליך מזורז)` --uses--> `ECharts library (vendor bundle)`  [EXTRACTED]
  /mnt/d/workdir/govdata/frontend/public/datasets/01aeaf5c-59a2-4ddc-a616-31b85621bfe2/content.html → frontend/public/lib/echarts.min.js
- `Dataset: 3111ae54-790a-4d02-9750-d51e1134b405` --uses--> `ECharts library (vendor bundle)`  [EXTRACTED]
  /mnt/d/workdir/govdata/frontend/public/datasets/3111ae54-790a-4d02-9750-d51e1134b405/content.html → frontend/public/lib/echarts.min.js
- `Dataset: c5ac01fb-c7ef-4e5e-ba81-e9e11c6f7bd9 (מאגר עמותות וחברות לתועלת הציבור)` --uses--> `ECharts library (vendor bundle)`  [EXTRACTED]
  /mnt/d/workdir/govdata/frontend/public/datasets/c5ac01fb-c7ef-4e5e-ba81-e9e11c6f7bd9/content.html → frontend/public/lib/echarts.min.js
- `main()` --calls--> `FirestoreStateStore`  [INFERRED]
  scripts/backfill_existing_pages.py → services/shared/firestore.py

## Hyperedges (group relationships)
- **manifest.json downstream consumers (build + runtime)** — nuxtconfig_manifest_json, nuxtconfig_categoryroutes, headersearch_fuse_index, browsebykind_counts, browsebyministry_top, latestdatasets_latest [INFERRED 0.90]
- **home page section composition** — hero_component, whatyouget_component, howitworks_component, browsebykind_component, browsebyministry_component, latestdatasets_component, calltoaction_component [INFERRED 0.80]
- **gov.il design tokens applied across chrome and cards** — tailwindconfig_govil_tokens, default_layout, datasetcard_component, hero_component [INFERRED 0.85]
- **datasets/[id].vue merges 3 SSG artifacts** —  [EXTRACTED 1.00]
- **useSeo + breadcrumb consumers across content pages** —  [EXTRACTED 1.00]
- **Pre-loaded dataset-page globals (Leaflet/MarkerCluster/ECharts/GovExplorer)** —  [EXTRACTED 1.00]
- **Dataset page pre-loaded globals** —  [EXTRACTED 1.00]
- **copy-libs build step** —  [EXTRACTED 1.00]
- **Cloud Run tick: scan -> select -> agent fan-out -> mark -> trigger publish** —  [EXTRACTED 1.00]
- **Publisher emits three artifacts from single Firestore source of truth** —  [EXTRACTED 1.00]
- **Agent session writes content.html to GCS + agent_data to Firestore** —  [EXTRACTED 1.00]
- **writers of Firestore sources/* doc** —  [EXTRACTED 1.00]
- **scanner pipeline: CKAN → ChangeDetector → Firestore** —  [EXTRACTED 1.00]
- **Dataset → save_dataset → SourceRecord** —  [EXTRACTED 1.00]
- **** — service_cloud_scheduler, service_builder_cloudrun, config_cloudbuild_publish [EXTRACTED 1.00]
- **** — step_fetch_pages, step_publish_artifacts, step_generate_and_deploy [EXTRACTED 1.00]
- **** — lib_echarts, lib_leaflet, lib_gov_explorer [EXTRACTED 1.00]

## Communities

### Community 0 - "ECharts vendor bundle (chunk 1)"
Cohesion: 0.02
Nodes (224): Ab(), af(), ag(), Ai(), Am(), An(), au(), ay() (+216 more)

### Community 1 - "ECharts vendor bundle (chunk 2)"
Cohesion: 0.04
Nodes (175): $(), A(), ac(), Ad(), ao(), aR(), at(), aw() (+167 more)

### Community 2 - "Page builder main + Cloud Run entry"
Cohesion: 0.04
Nodes (92): BaseSettings, Enum, Exception, http_entry(), HTTP entrypoint for the govdata-builder Cloud Run service.  One POST from Cloud, functions-framework HTTP entrypoint., _build_one(), _cli() (+84 more)

### Community 3 - "Voyage embeddings + scoring"
Cohesion: 0.03
Nodes (80): BaseModel, embed(), embedding_input(), Voyage AI embeddings for dataset metadata — used to compute relatedness across d, Compose the text fed to the embedder. Keep this deterministic so the     same da, Return a Voyage embedding vector, or None if the key isn't set / the     call fa, Page builder: Managed Agents controller that produces a per-dataset HTML page., agent_data_from_source() (+72 more)

### Community 4 - "Leaflet vendor bundle"
Cohesion: 0.04
Nodes (60): HS(), iv(), WS(), a(), Ae(), ai(), at(), be() (+52 more)

### Community 5 - "Managed Agent runtime + contracts"
Cohesion: 0.04
Nodes (60): Managed Agent env: govdata-env (cloud, unrestricted networking), Managed Agent: GovData Page Author (claude-sonnet-4-6), GCS bucket: govdata-il-staging, Agent output contract (content.html + agent_data.json, body-only), CKAN quirks: datastore_search_sql disabled; WAF needs browser User-Agent, Resource URLs use data.gov.il (no e. prefix), Design tokens aligned with www.gov.il, GOVIL_PALETTE chart color palette (+52 more)

### Community 6 - "Dataset SSG artifacts (data.json + agent_data + content.html)"
Cohesion: 0.06
Nodes (49): page_builder schema.py, data.gov.il CKAN host, e.data.gov.il IAP-gated host, AgentData interface, datasets/<id>/agent_data.json, awaitDatasetLibs, BreadcrumbItem, datasets/<id>/content.html (+41 more)

### Community 7 - "ECharts vendor bundle (chunk 3)"
Cohesion: 0.09
Nodes (40): aA(), ba(), br(), bt(), cA(), cv(), da(), ek() (+32 more)

### Community 8 - "ECharts vendor bundle (chunk 4)"
Cohesion: 0.12
Nodes (40): Al(), Ax(), bl(), Cl(), Cx(), dc(), Dl(), ec() (+32 more)

### Community 9 - "Build output artifacts (manifest, sitemap)"
Cohesion: 0.07
Nodes (38): datasets/<id>/agent_data.json (AgentData), datasets/<id>/content.html (GCS staged, body-only), datasets/<id>/data.json (DatasetMeta), public/data/manifest.json, .output/public/sitemap.xml, AgentData (agent-derived), DatasetMeta (scanner-derived), Manifest (+30 more)

### Community 10 - "Scanner CKAN domain models"
Cohesion: 0.07
Nodes (37): ChangeDetector, CKANClient, CKANError, Dataset (pydantic model), DatasetFilter, DatasetStatus enum, FirestoreStateStore, Organization (pydantic model) (+29 more)

### Community 11 - "Homepage Vue components"
Cohesion: 0.07
Nodes (27): app.vue Nuxt root template, counts by dataset_kind, useKindLabels() composable, top ministries by dataset count, relativeTimeHe() auto-import, layouts/default.vue, site footer (sources column → data.gov.il), gov-header chrome (+19 more)

### Community 12 - "ECharts vendor bundle (chunk 5)"
Cohesion: 0.11
Nodes (33): bi(), Cw(), Dw(), eS(), Ew(), fi(), Fw(), gI() (+25 more)

### Community 13 - "ECharts vendor bundle (chunk 6)"
Cohesion: 0.31
Nodes (20): ap(), dp(), Dy(), ep(), fp(), hp(), If(), ip() (+12 more)

### Community 14 - "Homepage screenshot (home.png)"
Cohesion: 0.11
Nodes (18): Dataset card: מאגר עמותות וחברות לתועלת הציבור (Justice Ministry, CSV·CSV·CSV), Dataset card: אנטנות סלולריות פעילות (Active cellular antennas, MoEP, CSV), Dataset card: מפלס ים המלח (Dead Sea level, water authority, CSV), Dataset count indicator: '3 מאגרים זמינים', Latest datasets card grid (3 cards), Design pattern: card-based layout with rounded-gov radii and subtle rules, Design pattern: minimal chrome (no nav links, brand-only header), Design pattern: gov.il blue palette (primary #0068f5, ink #0c3058, surface #f1f7ff) (+10 more)

### Community 15 - "Scanner package modules"
Cohesion: 0.24
Nodes (16): services/page_builder/schema.py, services/scanner/client.py, services/scanner/config.py, services/scanner/detector.py, services/scanner/filters.py, services/scanner/__init__.py, services/scanner/main.py, services/scanner/models.py (+8 more)

### Community 16 - "Dead Sea dataset screenshot"
Cohesion: 0.14
Nodes (17): כל הנתונים (All Data) Table - dates and water levels, Site Footer (GovData.IL), GovData.IL Header / Breadcrumb, תובנות מרכזיות (Key Insights) Section, ECharts Library (line chart rendering), GovExplorer Library (table / data exploration), Water Level Time-Series Line Chart, Metadata Card (publisher, license, format) (+9 more)

### Community 17 - "Antennas dataset screenshot"
Cohesion: 0.17
Nodes (16): Card-Based Sectioned Layout, Paginated Antennas Data Table, Cellular Antennas Dataset Page (אנטנות סלולריות פעילות), ECharts-rendered Visualizations, User Feedback Section (דירוג איכותי), Site Footer, gov.il Blue Palette (#0068f5 primary, ink navy), Site Header with GovData.IL Logo and Nav (+8 more)

### Community 18 - "Hebrew→Latin slug helper"
Cohesion: 0.23
Nodes (11): Deterministic Hebrew-aware slug helper.  URLs are routed by UUID, so the slug is, Return a stable, readable slug for `text`.      Strategy:       1. Normalize Uni, slugify(), Tests for services.shared.slug., test_collapses_runs_of_separators(), test_deterministic_across_calls(), test_empty_input_uses_fallback(), test_handles_mixed_hebrew_and_latin() (+3 more)

### Community 19 - "GovExplorer (deployed copy)"
Cohesion: 0.31
Nodes (6): clearChildren(), create(), debounce(), defaultRowDescriptor(), ensureStyles(), resolveEl()

### Community 20 - "GovExplorer (source script)"
Cohesion: 0.31
Nodes (6): clearChildren(), create(), debounce(), defaultRowDescriptor(), ensureStyles(), resolveEl()

### Community 21 - "Scanner datastore_total tests"
Cohesion: 0.39
Nodes (6): _ckan_response(), Tests for CKANClient.datastore_total., test_returns_none_on_4xx(), test_returns_none_on_unparseable_total(), test_returns_none_when_success_false(), test_returns_total_on_success()

### Community 26 - "useKindLabels composable"
Cohesion: 0.67
Nodes (1): infra/setup-agent.sh

### Community 27 - "Tailwind config (gov.il tokens)"
Cohesion: 0.67
Nodes (1): Thin legacy shim — kept only so existing imports don't break.  The real write-pa

### Community 28 - "build-sitemap script"
Cohesion: 0.67
Nodes (1): 4-step pipeline narrative

### Community 29 - "copy-libs script"
Cohesion: 0.67
Nodes (3): page_builder.main (HTTP entry), page_builder.pipeline, page_builder.writer (legacy shim)

### Community 30 - "Backfill + update-agent ops scripts"
Cohesion: 0.67
Nodes (3): agent/govdata-agent.yaml, Anthropic Managed Agents API, update-agent main()

### Community 36 - "Community 36"
Cohesion: 1.0
Nodes (2): go(entry) navigates to /datasets/<id>/, submit() handler

### Community 37 - "Community 37"
Cohesion: 1.0
Nodes (2): anthropic>=0.92.0 (managed agents beta), services/page_builder/requirements.txt

### Community 66 - "Community 66"
Cohesion: 1.0
Nodes (1): Create a Dataset from CKAN API response.

### Community 70 - "Community 70"
Cohesion: 1.0
Nodes (1): useManifest() composable (auto-import)

### Community 71 - "Community 71"
Cohesion: 1.0
Nodes (1): relativeTimeHe

### Community 72 - "Community 72"
Cohesion: 1.0
Nodes (1): services package

### Community 73 - "Community 73"
Cohesion: 1.0
Nodes (1): page_builder package

### Community 74 - "Community 74"
Cohesion: 1.0
Nodes (1): page_builder.publish

### Community 75 - "Community 75"
Cohesion: 1.0
Nodes (1): page_builder.selector

### Community 76 - "Community 76"
Cohesion: 1.0
Nodes (1): page_builder.session_runner

### Community 77 - "Community 77"
Cohesion: 1.0
Nodes (1): page_builder.related

### Community 78 - "Community 78"
Cohesion: 1.0
Nodes (1): page_builder.embeddings

### Community 79 - "Community 79"
Cohesion: 1.0
Nodes (1): page_builder.schema

### Community 80 - "Community 80"
Cohesion: 1.0
Nodes (1): writer.fire_build_hook

### Community 81 - "Community 81"
Cohesion: 1.0
Nodes (1): SessionResult dataclass

### Community 82 - "Community 82"
Cohesion: 1.0
Nodes (1): DownloadStatus enum

### Community 83 - "Community 83"
Cohesion: 1.0
Nodes (1): SOURCES_COLL = 'sources'

### Community 84 - "Community 84"
Cohesion: 1.0
Nodes (1): SCAN_RUNS_COLL = 'scan_runs'

### Community 85 - "Community 85"
Cohesion: 1.0
Nodes (1): Voyage embeddings optional (graceful degradation)

### Community 86 - "Community 86"
Cohesion: 1.0
Nodes (1): GCP region me-west1

### Community 87 - "Community 87"
Cohesion: 1.0
Nodes (1): Firebase/GCP project: govdata-il

### Community 88 - "Community 88"
Cohesion: 1.0
Nodes (1): requirements.txt (scanner deps)

## Ambiguous Edges - Review These
- `ECharts library (vendor bundle)` → `data.gov.il /api/3/action/datastore_search`  [AMBIGUOUS]
  frontend/public/lib/gov-explorer.js · relation: unrelated

## Knowledge Gaps
- **189 isolated node(s):** `Voyage AI embeddings for dataset metadata — used to compute relatedness across d`, `Compose the text fed to the embedder. Keep this deterministic so the     same da`, `Return a Voyage embedding vector, or None if the key isn't set / the     call fa`, `HTTP entrypoint for the govdata-builder Cloud Run service.  One POST from Cloud`, `functions-framework HTTP entrypoint.` (+184 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `useKindLabels composable`** (3 nodes): `infra/setup-agent.sh`, `main()`, `update-agent.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Tailwind config (gov.il tokens)`** (3 nodes): `fire_build_hook()`, `Thin legacy shim — kept only so existing imports don't break.  The real write-pa`, `writer.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `build-sitemap script`** (3 nodes): `HowItWorks.vue`, `4-step pipeline narrative`, `WhatYouGet.vue`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 36`** (2 nodes): `go(entry) navigates to /datasets/<id>/`, `submit() handler`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 37`** (2 nodes): `anthropic>=0.92.0 (managed agents beta)`, `services/page_builder/requirements.txt`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 66`** (1 nodes): `Create a Dataset from CKAN API response.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 70`** (1 nodes): `useManifest() composable (auto-import)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 71`** (1 nodes): `relativeTimeHe`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 72`** (1 nodes): `services package`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 73`** (1 nodes): `page_builder package`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 74`** (1 nodes): `page_builder.publish`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 75`** (1 nodes): `page_builder.selector`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 76`** (1 nodes): `page_builder.session_runner`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 77`** (1 nodes): `page_builder.related`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 78`** (1 nodes): `page_builder.embeddings`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 79`** (1 nodes): `page_builder.schema`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 80`** (1 nodes): `writer.fire_build_hook`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 81`** (1 nodes): `SessionResult dataclass`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 82`** (1 nodes): `DownloadStatus enum`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 83`** (1 nodes): `SOURCES_COLL = 'sources'`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 84`** (1 nodes): `SCAN_RUNS_COLL = 'scan_runs'`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 85`** (1 nodes): `Voyage embeddings optional (graceful degradation)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 86`** (1 nodes): `GCP region me-west1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 87`** (1 nodes): `Firebase/GCP project: govdata-il`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 88`** (1 nodes): `requirements.txt (scanner deps)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `ECharts library (vendor bundle)` and `data.gov.il /api/3/action/datastore_search`?**
  _Edge tagged AMBIGUOUS (relation: unrelated) - confidence is low._
- **Why does `T()` connect `ECharts vendor bundle (chunk 2)` to `ECharts vendor bundle (chunk 1)`, `Voyage embeddings + scoring`, `Leaflet vendor bundle`, `ECharts vendor bundle (chunk 3)`, `ECharts vendor bundle (chunk 4)`, `ECharts vendor bundle (chunk 5)`, `ECharts vendor bundle (chunk 6)`?**
  _High betweenness centrality (0.283) - this node is a cross-community bridge._
- **Why does `main()` connect `Voyage embeddings + scoring` to `ECharts vendor bundle (chunk 2)`?**
  _High betweenness centrality (0.272) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `T()` (e.g. with `ee()` and `ei()`) actually correct?**
  _`T()` has 4 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Voyage AI embeddings for dataset metadata — used to compute relatedness across d`, `Compose the text fed to the embedder. Keep this deterministic so the     same da`, `Return a Voyage embedding vector, or None if the key isn't set / the     call fa` to the rest of the system?**
  _189 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `ECharts vendor bundle (chunk 1)` be split into smaller, more focused modules?**
  _Cohesion score 0.02 - nodes in this community are weakly interconnected._
- **Should `ECharts vendor bundle (chunk 2)` be split into smaller, more focused modules?**
  _Cohesion score 0.04 - nodes in this community are weakly interconnected._