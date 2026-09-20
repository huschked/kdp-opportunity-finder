# KDP Opportunity Finder

A local, evidence-first research application for comparing nonfiction publishing niches. It combines observable market data, review-derived customer gaps, competition, economics, production suitability, expansion potential, and a separate confidence score.

This is not a book generator, sales predictor, or Amazon scraper. V1 begins with manual/synthetic data and preserves the source behind every claim.

## Implemented through Phase 5

Implemented:

- modular architecture and normalized SQLAlchemy schema
- SQLite initialization with foreign-key enforcement
- configurable score weights, UDI, confidence, and recommendation primitives
- repositories and niche creation service
- Streamlit dashboard/research navigation
- deterministic sample with 3 niches, 30 books, and 180 original synthetic reviews
- manual competitor creation and editing with append-only market snapshots
- validated book and review imports from uploaded CSV/JSON or pasted CSV
- preview-before-import, downloadable templates, and row-level rejection reports
- original/normalized review storage and exact duplicate detection
- competitor summaries and searchable/filterable review evidence
- strict review-analysis schemas and a deterministic offline mock provider
- optional OpenAI Structured Outputs provider with batched processing and usage capture
- content/logistics classification, semantic pain/praise clustering, and cache-aware reruns
- aggregate-to-review evidence drill-down, analysis-aware filters, and run history
- human pain-point rename/merge controls that survive later analysis runs
- six evidence-backed score components with inspectable inputs, formulas, missing-data behavior, and explanations
- confidence warnings for sparse, incomplete, stale, or concentrated evidence
- UDI factor explanations and confidence-gated recommendation labels
- append-only human score adjustments that preserve every automated value
- evidence-linked Markdown opportunity reports with in-app preview, download, and snapshot-staleness warnings
- evidence-grounded book specifications with cited design choices, labeled assumptions, explicit expert-review requirements, and append-only draft history
- decision-useful niche comparison with separate automated and human-adjusted scores, confidence, UDI, component charts, and evidence-coverage warnings
- human-controlled pipeline status management with stage counts, decision context, filters, required rationales, and append-only transition history
- traceable CSV and JSON exports for latest niche decisions, competitor books, and review evidence, with explicit scope, stable IDs, provenance, warnings, and missing values
- database, scoring, import, cleaning, market-summary, analysis, export, and Streamlit tests

Phase 5 is complete. See [ARCHITECTURE.md](ARCHITECTURE.md) for design and [KANBAN.md](KANBAN.md) for live execution status.

## Installation

Python 3.12+ is recommended.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` if you want to change defaults. No API key is needed; deterministic mock mode is the default.

## Run

```powershell
streamlit run app.py
```

Use **Load synthetic sample** in the sidebar to create three deliberately different scenarios:

- high demand / difficult competition
- attractive recurring gaps / manageable competition
- low competition / weak demand

The synthetic reviews are generated for this project and are not copied from Amazon.

## Analyze reviews

Open **Research**, choose **Analyze reviews**, select a niche, and keep **mock** selected for free local analysis. The first run extracts structured evidence; unchanged reviews are reused on later runs. Select **Force reanalysis** only when you intentionally want to bypass the cache.

To use OpenAI instead, set `OPENAI_API_KEY` and optionally `OPENAI_MODEL` in `.env`, then choose **openai** in the analysis form. Token totals are always stored. Cost estimates remain blank unless you supply verified current per-million-token prices through `OPENAI_INPUT_COST_PER_MILLION` and `OPENAI_OUTPUT_COST_PER_MILLION`.

Open **Niche detail** to filter analyzed reviews or inspect **Pain points**, **Praise**, and **Analysis history**. Shipping, seller, and buyer-mismatch complaints remain in the per-review extraction for auditability but are excluded from opportunity aggregates.

## Score a niche

Open **Niche detail**, select **Decision**, and choose **Calculate a new snapshot**. The result shows the automated opportunity score, confidence, UDI, evidence warnings, every component factor, raw aggregate inputs, and missing observations. This uses stored market and review evidence only; it does not call an API.

You can record a human decision adjustment with a required rationale. The adjustment creates another snapshot and leaves the automated score, component values, confidence, and weights unchanged.

Open the dedicated **Opportunity report** page in the sidebar—or select it from the Niche detail view—to preview and download the latest report. Score claims cite the immutable snapshot, while market and review findings cite their stored book, pain-point, praise-feature, and review IDs. If books or reviews were added after scoring, the report tells you to recalculate before relying on the decision.

Open **Book specification** in the sidebar to generate a local planning draft from the latest score and evidence. Every product decision is labeled **Evidence-backed**, **Assumption to validate**, or **Risk review required**. The preview and Markdown download include supporting evidence IDs, validation questions, accuracy/rights safeguards, and the source score snapshot. Generating again creates a new draft rather than overwriting history.

Open **Compare** to select two to six niches. The page shows evidence-comparability warnings before ranking, preserves automated and human-adjusted scores as separate fields, and compares confidence, UDI, components, warning counts, and stored coverage inputs. Unscored niches stay visible but are not assigned a rank.

Open **Pipeline** to review counts across every workflow stage, filter niches, and retain their latest decision context. Status changes are manual, require a rationale, and append a transition-history record. Changing a local pipeline status never recalculates a score or publishes, rejects, or archives anything outside this application.

Open **Exports** to download the latest niche decisions across all niches or one selected niche, or to export a selected niche's competitor books and review evidence. CSV files keep missing values blank and encode nested evidence as JSON text; JSON files preserve native nulls and nested objects and include a manifest describing the exact scope. Stable niche, book, review, source, market-snapshot, score-snapshot, analysis, pain-link, and praise-link IDs are included where applicable.

## Import data

Open **Research**, select **Import books** or **Import reviews**, and download a CSV or JSON example. Every batch is validated before persistence. The preview lists accepted rows and every rejected row with its reason.

Review imports reference books through `book_identifier`, which must match one unambiguous book `source_identifier` in the selected niche. Title-based fuzzy matching is intentionally not used.

## Test

```powershell
pytest
```

## Data and configuration

- Default database: `kdp_opportunity_finder.db` in the project root.
- Override with `KDP_DATABASE_URL` in `.env`.
- Scoring weights and targets: `config/scoring.yaml`; the six weights must total 1.0 and each snapshot stores the exact policy used.
- LLM provider: `KDP_LLM_PROVIDER=mock` by default.

## Scoring direction

All components are 0–100. A higher competition score means a more accessible competitive environment. The opportunity score is weighted, while confidence is displayed separately and gates recommendation language. No missing market value is fabricated.

## Limitations

Sample scores are controlled scenarios used to validate the model and UI, not marketplace findings. The current app does not collect Amazon data, estimate sales, or automatically decide whether to publish a title. Mock analysis and decision scoring are fully local; OpenAI analysis remains optional. Those boundaries are deliberate.
