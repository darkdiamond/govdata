# Promotion / backlinks — submission log

Plan: `~/.claude/plans/scan-the-website-and-agile-moore.md` (approved 2026-06-12).
Positioning used everywhere: free Hebrew AI-explainer layer over the official
data.gov.il portal; AI authorship always disclosed.

## Executed 2026-06-12

| Target | Action | Status | Link / note |
|---|---|---|---|
| danielrosehill/Israel-Open-Data-Resources | PR adding govil.ai to "Government & data.gov.il tooling" | **Open** | https://github.com/danielrosehill/Israel-Open-Data-Resources/pull/1 |
| danielrosehill/Israeli-AI | PR adding govil.ai to `agents.md` | **Open** | https://github.com/danielrosehill/Israeli-AI/pull/1 |
| okfn/dataportals.org | Eligibility question (aggregator vs portal) before any PR | **Open** | https://github.com/okfn/dataportals.org/issues/417 |
| Open Data Inception (opendatasoft) | Google Form submission (name/org/Israel/URL/topics/coords) | **Submitted** | Confirmation: "available on the online database within a couple hours" — check https://opendatainception.io/ map (Israel) |
| Civic Tech Field Guide | Fillout listing form (Tool or platform, Israel HQ+serve, long description) | **Submitted** | Confirmation email will arrive at admin@govil.ai with the listing link |
| IndexNow (Bing/Yandex/Seznam) | Key file `frontend/public/d6ede06d967d8c5ae326761d20ad54f3.txt` + post-deploy ping step in publish.yml | **Shipped** | Verify in next publish run logs: `[indexnow] pinged N URLs -> HTTP 200` |
| Google Dataset Search | Checked indexing | **Not indexed yet** | `site:govil.ai` returns nothing (2026-06-12). JSON-LD is in place; GSC sitemap submission (owner action) should accelerate. Re-check in 2–4 weeks. |

## Skipped, with reasons

- **lirantal/awesome-opensource-israel** — list is for open-source projects; the
  govdata repo is private. Revisit if the repo is ever open-sourced.
- **awesomedata/awesome-public-datasets (apd-core)** — datasets only, explicit
  "No reputation promotion!" rule. govil.ai is a tool, not a dataset.
- **re3data.org** — research data repositories only.
- **Wikipedia external links, paid/low-quality directories** — policy/penalty risk.

## Follow-ups

- [ ] Watch the two PRs + the OKFN issue for maintainer feedback (respond promptly).
- [ ] If OKFN says aggregators qualify → PR adding govil.ai to `data/portals.csv`.
- [ ] Confirm Open Data Inception map shows govil.ai (a few hours after submission).
- [ ] Confirm Civic Tech Field Guide listing email at admin@govil.ai.
- [ ] Owner actions: see `outreach-kit.md` (GSC + Bing WMT, data.gov.il, HaSadna, press, communities).
- [ ] In ~4 weeks: GSC Links report — expect first referring domains from the four directory listings.
