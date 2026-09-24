# KDP Opportunity Finder — Kanban

Last updated: 2026-09-23

This board tracks execution. `ARCHITECTURE.md` remains the authority for system design, data relationships, and scope decisions.

## Progress

| Phase | State | Outcome |
|---|---|---|
| Phase 1 — Foundation | Done | Architecture, database, sample data, scoring primitives, navigation, tests |
| Phase 2 — Ingestion and browsing | Done | Reliable manual/CSV/JSON input and evidence browsing |
| Phase 3 — Evidence extraction | Done | Structured review analysis, clustering, caching, and traceability |
| Phase 4 — Decisions | Done | Evidence-backed scoring, confidence, UDI, explanations, gating, and additive overrides |
| Phase 5 — Outputs and workflow | Done | Reports, specifications, comparison, pipeline, and traceable exports |
| Phase 6 — Hardening | In progress | Test matrix, guarded migrations, operational errors, performance, and UI hardening complete; final documentation is next |

## In progress

No active card.

## Ready

### P6-DOCS-01 — Final README, import references, limitations, and roadmap

- **Priority:** P1
- **Deliverable:** Bring the README and supporting references in line with the completed V1 workflows, setup requirements, known limitations, and post-V1 roadmap.
- **Dependencies:** `P6-UI-01`.
- **Verification:** Documentation link/command review, clean-environment setup walkthrough, full regression suite, and running-app smoke test.

## Backlog

### Phase 5 — Outputs and workflow

No remaining Phase 5 cards.

### Phase 6 — Hardening

No remaining backlog cards; `P6-DOCS-01` is ready.

## Blocked

No blocked cards.

Use this section only when a card cannot progress without a user decision, missing input, unavailable dependency, or external state change. Include the blocker and the exact unblock condition.

## Done

### P1-ARCH-01 — Architecture and scope

- Modular-monolith architecture documented.
- Design tensions and assumptions resolved.
- V1 and deliberate non-V1 automation boundaries recorded.

### P1-DB-01 — Database foundation

- Normalized SQLAlchemy entities implemented.
- Provenance, historical snapshots, analysis runs, score snapshots, and evidence joins included.
- SQLite foreign keys enabled.

### P1-SCORE-01 — Scoring primitives

- Editable weights implemented.
- Overall score, confidence, UDI, normalization, and confidence-gated recommendation functions implemented.

### P1-SAMPLE-01 — Synthetic market scenarios

- Three niches, thirty books, and 180 original synthetic reviews generated.
- Scenarios cover difficult competition, attractive gaps, and weak demand.

### P1-UI-01 — Streamlit shell

- Dashboard, research creation, navigation, metrics, tables, warnings, and phase-aware placeholders implemented.

### P1-VERIFY-01 — Phase 1 verification

- Eight tests passing.
- Python compilation successful.
- Streamlit health endpoint returned HTTP 200.

### P2-IMPORT-01 — Validated import foundation

- Shared Pydantic schemas validate CSV and JSON consistently.
- Row-level issues, checksums, provenance, counts, and batch status are retained.
- Malformed rows are reported rather than silently dropped.

### P2-IMPORT-02 — Book ingestion workflows

- Manual add/edit, uploaded CSV/JSON, pasted CSV, preview-before-persist, and downloadable templates implemented.
- Duplicate source identifiers are rejected with an explanation.
- Manual edits append market snapshots rather than erasing observed history.

### P2-IMPORT-03 — Review ingestion and cleaning

- Raw text is preserved while normalized text and SHA-256 hashes are stored separately.
- Exact duplicates, unknown books, and ambiguous book identifiers are reported.
- Valid rows in partially invalid batches remain importable.

### P2-BROWSE-01 — Competitor table and summaries

- Search, format filtering, sortable market fields, medians, review concentration, and a focused chart implemented.
- Missing observations are excluded rather than estimated.

### P2-BROWSE-02 — Review browser

- Book, rating, text, and date filters implemented.
- Source metadata plus original and normalized text are inspectable.

### P2-VERIFY-01 — Phase 2 verification

- Seventeen tests passing, including import, cleaning, filtering, market summaries, snapshots, and Streamlit navigation.
- Python compilation successful.
- Streamlit health and root endpoints returned HTTP 200.

### P3-LLM-01 — Structured review-analysis schemas

- Strict, versioned Pydantic contracts cover sentiment, topics, features, pain points, praise, outcomes, reader level, improvements, severity, solvability, and confidence.
- Shipping, seller, and buyer-mismatch complaints cannot validate as book-solvable opportunities.

### P3-LLM-02 — Provider protocol and deterministic mock

- A shared provider protocol returns the same validated schemas in every mode.
- Deterministic mock analysis runs locally without credentials and supports repeatable end-to-end tests.
- Failed provider runs are recorded without replacing prior successful evidence.

### P3-LLM-03 — Optional OpenAI provider

- The optional provider uses SDK-native Pydantic Structured Outputs for review extraction and semantic clustering.
- Refusals or missing parsed output become explicit contract errors.
- The integration contract is tested with an injected client; live credential-dependent execution remains user verification.

### P3-PIPE-01 — Batched, cached analysis pipeline

- Review batches are bounded and cache keys include content, provider, model, schema, and prompt versions.
- Only a fully successful provider result replaces derived evidence; failed runs preserve the last successful analysis.
- Token usage and optionally configured cost estimates are stored on each run; OpenAI client retries transient failures twice.

### P3-PAIN-01 — Relevant pain-point extraction

- Content, design, and format/usability problems are separated from logistics and buyer mismatch.
- Only solvable book problems enter opportunity aggregates; excluded complaints remain traceable in per-review structured results.

### P3-PAIN-02 — Canonical pain-point clustering

- Similar candidate labels become canonical groups with review and book counts.
- Human rename and merge controls preserve grouping decisions across later analysis runs.

### P3-PRAISE-01 — Praise and value aggregation

- Praised features, desired outcomes, and purchase-value signals are retained per review and aggregated by canonical feature.

### P3-EVIDENCE-01 — Evidence drill-down

- Niche detail views expose pain-point and praise summaries, supporting excerpts, original reviews, analysis-aware review filters, and run history.

### P3-VERIFY-01 — Phase 3 verification

- Twenty-four tests pass, including schemas, positive/mixed/irrelevant extraction, OpenAI provider contract, caching, failure atomicity, logistics exclusion, human regrouping, and Streamlit navigation.
- Python compilation completed successfully.
- Streamlit health and root endpoints returned HTTP 200.

### P4-SCORE-01 — Evidence-backed scoring components

- Demand, competitive opportunity, customer gap, economics, AI suitability, and expansion scores are calculated from observable stored inputs.
- Every component snapshot retains normalized factors, aggregate inputs, formula text, missing observations, and explanation text.
- Customer-gap scoring uses only solvable, review-linked evidence; no missing marketplace value is estimated.

### P4-CONF-01 — Confidence and decision gating

- Book and review sample size, cross-book coverage, field completeness, analysis coverage, evidence distribution, and recency contribute separately to confidence.
- Sparse, incomplete, stale, and concentrated data produce exact warnings.
- Scores below the confidence gate always return `Needs more data` regardless of opportunity score.

### P4-UDI-01 — UDI factor explanations

- UDI preserves demand, gap, solvability, and competitive-accessibility factors plus an explanation of the multiplicative constraint.

### P4-OVERRIDE-01 — Additive human overrides

- Human adjustments require a rationale and create a new snapshot.
- Automated components, total, confidence, policy, and weights remain unchanged and auditable.

### P4-DECISION-01 — Decision view

- Niche detail now exposes score metrics, recommendation gating, warnings, component tables, formula drill-down, UDI factors, overrides, and history.
- Settings shows active weights and the editable configuration location.

### P4-VERIFY-01 — Phase 4 verification

- Thirty-one tests pass, including component boundaries, sparse/concentrated evidence, three synthetic market scenarios, snapshot history, overrides, and Streamlit recalculation.
- Python compilation completed successfully.

### P5-REPORT-01 — Evidence-linked opportunity report

- The latest explainable score snapshot generates a deterministic Markdown opportunity report with a dedicated sidebar page, Niche detail view, preview, and download.
- Decision, component, confidence, and UDI claims cite the immutable score snapshot; market and review findings cite book, pain-point, praise-feature, and review evidence IDs.
- Confidence warnings and component-level missing observations remain prominent, and corpus changes after scoring trigger a recalculate warning.
- Reports refuse unscored or legacy snapshots rather than silently omitting evidence links.
- The method boundary explicitly prohibits sales prediction and automatic publish decisions.

### P5-REPORT-VERIFY-01 — Opportunity report verification

- Thirty-five tests pass, including report snapshots across all three synthetic markets, evidence citation integrity, sparse-data warnings, snapshot staleness, and Streamlit report navigation.
- Python compilation completed successfully.

### P5-CONCEPT-01 — Evidence-grounded book specification

- A deterministic local generator creates append-only book-specification drafts from the latest explainable score snapshot and current evidence.
- Target reader, core problem, desired outcome, positioning, content modules, product features, and format guidance are individually marked as evidence-backed or assumptions to validate.
- Evidence-backed choices cite pain-point, praise-feature, or supporting review IDs; uncited claims cannot validate as evidence-backed.
- Regulated-topic, expertise, asset-rights, accuracy, and fact-checking requirements remain explicit even when keyword screening finds no risk term.
- A dedicated sidebar page exposes generation, evidence/assumption metrics, Markdown preview/download, snapshot-staleness warnings, and draft history.

### P5-CONCEPT-VERIFY-01 — Book specification verification

- Forty-one tests pass, including sparse and analyzed evidence, citation integrity, regulated-topic review, append-only history, score/analysis staleness, and Streamlit generation.
- Python compilation completed successfully.

### P5-COMPARE-01 — Decision-useful niche comparison

- Selected niches use their latest immutable score snapshots and remain visible when unscored.
- Automated score, human-adjusted score, decision score, confidence, UDI, components, warning counts, and coverage inputs remain separate.
- Evidence-comparability warnings appear before ranking for missing scores, sparse evidence, materially unequal confidence or coverage, and differing scoring versions.
- Focused score-versus-confidence and component charts use one-decimal display precision and preserve the confidence gate.

### P5-COMPARE-VERIFY-01 — Niche comparison verification

- Forty-four tests pass, including decision-score ordering, missing-score handling, unequal-confidence warnings, metric separation, and Streamlit multiselect interaction.
- Python compilation completed successfully.
- Temporary Streamlit server health and root endpoints returned HTTP 200.

### P5-PIPELINE-01 — Status controls and pipeline view

- Pipeline metrics and stage counts cover every defined workflow status, including zero-count stages.
- Search and status filters retain latest decision context without combining automated score, human adjustment, confidence, UDI, or evidence-warning counts.
- Manual status changes validate defined status values, require a rationale, and append prior status, new status, rationale, and timestamp to an audit history.
- Scores and recommendations never change pipeline status automatically, and status changes do not alter score snapshots.

### P5-PIPELINE-VERIFY-01 — Pipeline verification

- Forty-nine tests pass, including persisted transitions, invalid/no-op/unexplained change rejection, history, count consistency, filtering, score/status separation, and Streamlit interaction.
- Python compilation completed successfully.
- Additive initialization created the status-transition table in the existing local SQLite database without replacing current data.
- Temporary Streamlit server health and root endpoints returned HTTP 200.

### P5-EXPORT-01 — Traceable CSV and JSON exports

- A dedicated Exports page downloads latest niche decisions, competitor books, or review evidence as explicitly named CSV and JSON files.
- Decision exports preserve score-snapshot IDs, automated and human-adjusted scores, effective decision score, confidence, UDI, warnings, missing observations, weights, explanations, and evidence-coverage inputs as separate fields.
- Book and review exports preserve stable niche, source, record, market-snapshot, analysis, and derived evidence-link IDs where applicable.
- CSV leaves missing values blank and represents nested evidence as JSON text; JSON retains native nulls, arrays, and objects and adds a scope and warning manifest.

### P5-EXPORT-VERIFY-01 — Export verification

- Fifty-three tests pass, including latest-snapshot selection, schema, provenance, missing-value preservation, niche filtering, evidence-link IDs, and all three Streamlit export states.
- Python compilation, repository whitespace validation, and a temporary Streamlit health/root smoke test completed successfully.

### P6-TEST-01 — Full critical-business-logic test matrix

- `TEST_MATRIX.md` maps every critical V1 workflow to happy-path, boundary/uncertainty, and failure/guardrail evidence.
- The suite adds explicit protection for rejected writes, duplicate records, invalid human overrides, cross-niche isolation, missing prerequisites, provider failure atomicity, and empty Streamlit page states.
- No-fabrication, evidence-provenance, immutable-history, human-control, failure-atomicity, and cross-niche-isolation guardrails are traceable to named tests.
- Residual live-provider, browser/accessibility, concurrency, scale, and operational-diagnostics risks are assigned to later Phase 6 cards.

### P6-TEST-VERIFY-01 — Test-matrix verification

- Seventy-three tests pass, up from fifty-three before the hardening card.
- Python compilation and repository whitespace validation pass.
- AppTest covers empty and seeded top-level workflows through `app.py`; a temporary Streamlit server returned HTTP 200 for health and root endpoints.

### P6-MIGRATE-01 — Alembic baseline and migration workflow

- Alembic configuration, application metadata integration, and explicit upgrade/downgrade operations establish revision `20260921_0001` as the reviewed current-schema baseline.
- Startup upgrades empty and versioned databases, stamps only an exact unversioned schema match, and refuses partial or unexpected unversioned schemas without changing them.
- The existing local database was stamped without recreating its application tables; its 4 niches, 32 books, 181 reviews, 14 score snapshots, and 1 status transition remained intact.
- `MIGRATIONS.md` documents backup hashing, status and upgrade commands, revision review, verification, and the no-downgrade recovery boundary.
- A byte-identical local database backup is retained under ignored `backups/` storage.

### P6-MIGRATE-VERIFY-01 — Migration workflow verification

- Seventy-six tests pass, including fresh upgrade, idempotent startup, exact metadata comparison, populated legacy-schema adoption, data preservation, and incompatible-schema refusal.
- Python compilation and repository whitespace validation pass.
- Alembic reports revision `20260921_0001 (head)`, and the direct bootstrap reports the database is current.
- A temporary Streamlit server returned HTTP 200 for health and root endpoints after the migration startup change.

### P6-ERROR-01 — Structured logging and user-facing error handling

- Rotating JSON-lines logs retain operation names, short reference IDs, allow-listed entity context, exception classes, and traceback frame locations.
- Structured failure records omit exception messages and redact credentials, authorization values, review text, body content, and any context field outside the safe allow-list.
- Startup/schema, page rendering, sample loading, imports, provider analysis, scoring, exports, pipeline changes, specification generation, and evidence corrections now present concise recovery guidance instead of raw exception text.
- Import validation and committed batches record counts and stable IDs without logging uploaded contents or filenames.
- The log path and level are configurable through `.env`, and local log files remain outside Git.

### P6-ERROR-VERIFY-01 — Error-handling verification

- Eighty-one tests pass, including JSON structure, safe context, secret/review redaction, durable warning references, UI recovery messaging, transaction rollback, provider failure atomicity, and real-entrypoint incompatible-schema recovery.
- The incompatible-schema test preserves its existing database row and does not add an Alembic version marker.
- Python compilation and repository whitespace validation pass.
- A temporary Streamlit server returned HTTP 200 for health and root endpoints after the error-boundary changes.

### P6-PERF-01 — Query, batch, and rerun performance review

- `PERFORMANCE.md` and `scripts/profile_performance.py` measure dashboard, niche detail, comparison, pipeline, exports, import preview, scoring, full analysis, and cached analysis against a disposable migrated 3-niche/30-book/180-review database.
- Dashboard reads dropped from 7 SQL statements to 4, pipeline from 5 to 3, competitor detail from 2 to 1, and review detail from 5 to 4 while preserving returned totals.
- Latest score and market rows are selected deterministically in SQL, so historical snapshot depth no longer causes comparison, pipeline, dashboard, or book export to materialize every prior snapshot.
- Import duplicate checks query only candidate keys in explicit 400-pair batches; analysis extraction remains capped at 50 reviews per provider call.
- Fully cached analysis runs retain an audit record and exact evidence counts while making zero extraction or clustering provider calls; new or changed reviews still invalidate their extraction cache.
- Pipeline filters submit together and reuse the loaded snapshot, niche detail loads only the selected view's data, and no cross-rerun database cache can serve stale decision evidence.
- Full-scope exports remain untruncated; the visible preview limit does not alter CSV/JSON records or manifest totals.

### P6-PERF-VERIFY-01 — Performance verification

- Eighty-six tests pass, including latest-row history/tie boundaries, single-statement totals, query-free pipeline filtering, the 400-pair import boundary, the 50-review analysis batch cap, zero-call cache reuse, and new-content invalidation.
- The disposable performance profile completed all representative workflows and recorded SQL counts, returned totals, and median local timings.
- Streamlit AppTest passed the updated form interaction; Python compilation and repository whitespace validation passed.
- A temporary Streamlit server returned HTTP 200 for health and root endpoints after the performance changes.

### P6-UI-01 — Accessibility, responsive layout, empty states, and visual cleanup

- Shared native Streamlit layout patterns give every primary no-data state a clear explanation and concrete next step without hiding uncertainty or inventing evidence.
- Dashboard metrics, decision views, import previews, and detail summaries use responsive containers, concise help text, explicit icons, and readable metric names while retaining separate scores, confidence, warnings, provenance, and manual workflow status.
- Top-level pages and evidence panels use consistent headings, bordered groups, sentence-case labels, stable widget keys, and explicit status text instead of relying on color alone.
- The review-analysis provider choice now uses a responsive segmented control; no custom CSS, unsafe HTML, or fixed-width desktop-only layout was introduced.

### P6-UI-VERIFY-01 — UI-hardening verification

- Eighty-seven tests pass, including actionable empty states across all primary pages, empty and seeded navigation, provider-control behavior, and every existing business-logic guardrail.
- Python compilation and repository whitespace validation pass, and the deprecated-layout scan finds no dividers, horizontal radios, `use_container_width`, unsafe HTML, or raw `st.html` use in the app UI.
- Rendered browser review at 1440×900 and 390×844 confirms the dashboard and dense decision detail remain readable with no document-level horizontal overflow.
- A temporary Streamlit server returned HTTP 200 for health and root endpoints; browser diagnostics reported no application errors, only non-blocking Vega scale warnings from Streamlit's chart renderer.

## Scope guardrails

The following remain outside V1 unless explicitly moved onto the board:

- Amazon scraping or anti-automation bypass.
- Automated Amazon search or keyword-volume collection.
- BSR-to-sales claims or invented sales estimates.
- Scheduled refreshes, alerts, and full trend tracking.
- Cover analysis or automated book production.
- Automatic publish/reject decisions.
- Cloud deployment, authentication, and multi-user support.

## Board rules

1. A card moves to **In progress** only when implementation begins.
2. Keep at most two active cards unless work is intentionally parallelized.
3. A card reaches **Done** only after its acceptance criteria and verification pass.
4. Record newly discovered scope as a new card; do not silently expand an active card.
5. Add blockers immediately and state the exact condition needed to resume.
6. Update the progress table and `Last updated` date whenever a phase changes state.
