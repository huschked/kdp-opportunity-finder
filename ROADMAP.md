# V1 boundaries and post-V1 roadmap

## Current status

The planned V1 scope is complete as of 2026-09-24. The local application supports evidence ingestion, review analysis, decision scoring, reports, specifications, comparison, workflow status, exports, migrations, diagnostics, bounded performance, responsive pages, and regression coverage.

The completed execution record is in [KANBAN.md](KANBAN.md). This roadmap records possibilities, not active commitments. Future work begins only after a specifically scoped card is added to the Kanban board with acceptance criteria and verification.

## Deliberate V1 limitations

### Evidence acquisition

- V1 accepts manual entries and user-supplied CSV/JSON only.
- It does not search Amazon, scrape product/review pages, bypass automation controls, or collect keyword-volume data.
- It does not verify that imported material is complete, representative, current, or licensed for the user's intended use.
- Current competitor values can be updated manually, but V1 does not schedule refreshes or present a longitudinal trend-analysis workflow.

### Decision meaning

- Scores describe the evidence stored under the versioned local policy. They do not predict unit sales, revenue, royalties, profit, ranking, or future demand.
- Missing data reduces coverage/confidence or stays visibly missing; it is never replaced with invented marketplace values.
- Confidence gates recommendation language but cannot prove that a market opportunity exists.
- Reports and book specifications organize evidence and validation questions. They are not professional advice, fact verification, rights clearance, or finished publishing assets.

### Analysis quality

- The mock provider is deterministic workflow evidence, not human-level qualitative research.
- The optional OpenAI adapter is contract-tested without spending live API credits. Live availability, model changes, latency, cost, refusals, and output quality remain external variables.
- English review analysis is the initial target. Unicode source text is retained, but multilingual extraction and clustering quality have not been established.
- Human review is still required for cluster corrections, regulated subjects, expertise claims, factual accuracy, and any decision based on sparse or concentrated evidence.

### Operation and scale

- V1 assumes one trusted local user, one local filesystem, and one SQLite database.
- It has no login, roles, cloud synchronization, multi-user conflict handling, or multi-process write guarantee.
- The representative profile uses three niches, 30 books, and 180 reviews. Larger corpora need separate capacity testing even though provider batches and duplicate lookups are bounded.
- Backups are manual. Logs are local rotating JSON lines; external monitoring, encrypted backup, disaster recovery, and operating-system failure handling are not included.
- Automated tests cover application behavior, and responsive browser checks cover representative desktop/mobile layouts. Full assistive-technology certification and every browser/download combination remain manual validation responsibilities.

## Candidate post-V1 directions

The order below reflects logical dependency, not a committed delivery sequence.

### 1. Research-quality controls

- Add explicit research-session dates, source-quality notes, and freshness targets.
- Add duplicate-resolution and data-quality review queues for large imports.
- Add validation checklists that must be completed before a niche can move to later pipeline stages.
- Expand multilingual fixtures and measure extraction/clustering quality before claiming language support.

### 2. Longitudinal evidence

- Add an intentional manual refresh workflow that appends dated market snapshots.
- Visualize observable price, rating, review-count, and rank history without converting rank into sales.
- Add stale-evidence views and user-controlled reminders without automatic marketplace collection.

### 3. Approved external sources

- Evaluate official or licensed data sources one at a time, including terms, attribution, rate limits, cost, provenance, and deletion requirements.
- Build replaceable source adapters only after the source is approved; preserve raw observations and stable source references.
- Keep anti-bot bypass, prohibited scraping, fabricated keyword volume, and opaque sales-estimation services out of scope.

### 4. Analysis evaluation

- Build a reviewed evaluation set for pain relevance, solvability, praise, reader outcomes, and cluster quality.
- Compare providers/models against the same stored source evidence and versioned schema.
- Add user-approved reprocessing tools that show the impact of prompt, schema, or model changes before replacing derived evidence.

### 5. Collaboration and deployment

- Define authentication, authorization, encryption, backup, and audit requirements before any cloud deployment.
- Replace SQLite only if measured concurrency or scale requires it.
- Design workspace isolation and conflict rules before enabling multiple editors.
- Add CI packaging and supported deployment targets only after secrets, migrations, storage, and rollback are specified.

### 6. Publishing-workflow integrations

- Consider project-management, editorial, or asset handoff integrations that export reviewed decisions without auto-publishing.
- Keep manuscript generation, cover scoring/generation, advertising automation, and automatic publish/reject decisions outside the decision tool unless each becomes a separately governed project.

## How a roadmap item becomes work

Before implementation, create a Kanban card that states:

1. the user decision or workflow the feature improves;
2. the authorized data source and provenance requirements;
3. how uncertainty and missing information remain visible;
4. what remains under explicit human control;
5. the migration, privacy, failure, and rollback boundaries; and
6. automated plus running-application verification.

This keeps future additions consistent with the V1 principle: research evidence may support a decision, but the software must not present unsupported claims as marketplace findings.
