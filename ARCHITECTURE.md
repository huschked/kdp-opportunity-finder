# KDP Opportunity Finder — V1 Architecture

## Product boundary

KDP Opportunity Finder is a local decision-support application. It stores user-supplied marketplace observations, mines synthetic or legitimately obtained review text, preserves the evidence behind every conclusion, and compares niches without pretending that an LLM suggestion or a sparse data set is market proof.

V1 deliberately uses a modular monolith:

```text
Streamlit UI -> services -> repositories -> SQLAlchemy -> SQLite
                    |              |
                    |              +-> provenance and immutable source records
                    +-> quantitative analysis / LLM provider abstraction
```

This keeps business rules out of Streamlit callbacks while avoiding infrastructure that a local research tool does not need.

## Modules

- `collectors/`: manual, CSV, and JSON adapters that return validated domain inputs. No Amazon scraper.
- `models/`: normalized SQLAlchemy entities and Pydantic transport/LLM schemas.
- `db/`: engine/session lifecycle and repositories.
- `analysis/`: deterministic metrics, clustering, scoring, confidence, and explanations.
- `llm/`: provider protocol, structured schemas, deterministic mock, and optional OpenAI provider.
- `services/`: transactions and workflows used by both UI and tests.
- `pages/`: thin Streamlit render functions.
- `config/`: environment settings and editable scoring configuration.

## Database schema

```text
data_sources 1---* import_batches
data_sources 1---* books
data_sources 1---* reviews

niches 1---* books 1---* reviews 1---0..1 review_analyses
   |                        |
   |                        *---* pain_points (review_pain_points)
   |                        *---* praise_features (review_praise_features)
   |
   +---* pain_points
   +---* praise_features
   +---* analysis_runs
   +---* score_snapshots
   +---* book_concepts

books 1---* market_snapshots
```

Important choices:

- `reviews.raw_body` is immutable source text; `normalized_body` and `normalized_hash` support cleaning and exact duplicate detection.
- Aggregate pain points remain traceable through `review_pain_points`; mention counts are derived, not the only evidence retained.
- Current book fields make browsing fast, while `market_snapshots` allows later price/rating/review-count/BSR history.
- `analysis_runs` records provider, model, prompt version, parameters, result, status, usage, and cost.
- `score_snapshots` stores component values, explanation JSON, weights, automated total, optional human total, and confidence. Raw observations stay in their source tables.
- Human overrides are additive fields or new snapshots; automated values are not overwritten.

SQLite uniqueness rules prevent duplicate source identifiers within a source and duplicate normalized review text within a book. Nullable marketplace fields remain nullable; missing facts are never filled with estimates.

## Scoring model

All components are normalized to 0–100 before weighting:

```text
Overall = Demand × .25
        + Competitive opportunity × .20
        + Customer gap × .25
        + Economics × .15
        + AI suitability × .10
        + Expansion × .05
```

Competition is directional: 100 means unusually favorable, 0 means extremely difficult. Weights live in `config/scoring.yaml` and are validated to total 1.0.

The component layer will expose inspectable sub-scores:

- Demand: rank coverage/strength when supplied, review traction, review recency, competitor activity.
- Competitive opportunity: review concentration, incumbent scale, ratings headroom, publication age, publisher concentration.
- Customer gap: recurring complaint strength, cross-book prevalence, severity, and solvability.
- Economics: observed price/format/page profile plus configurable production assumptions.
- AI suitability: research and verification burden, regulated-topic risk, expertise, and asset requirements.
- Expansion: evidence-backed adjacent formats, levels, use cases, and subtopics.

Confidence is separate from opportunity. It combines book sample size, review sample size, cross-book coverage, field completeness, collection recency, and analysis completeness. A high score with low confidence is displayed as “needs more data,” not as a recommendation.

The Unmet Demand Index is a diagnostic, not a replacement overall score:

```text
UDI = demand_strength
    × gap_strength
    × solvability
    × competitive_accessibility
```

Each normalized factor is divided by 100 before multiplication and the result is returned on a 0–100 scale.

## V1 screens

1. **Dashboard** — corpus totals, stage distribution, ranked opportunities, recent analyses, and confidence warnings.
2. **Research** — create/edit niche, add books, import books/reviews, and run analysis.
3. **Niche Detail** — overview, competitors, reviews, pain points with evidence, praise, score explanations, concept, raw data, history.
4. **Compare** — side-by-side scores, confidence, UDI, and only decision-useful charts.
5. **Pipeline** — status controls for discovered through published, plus rejected/archived.
6. **Settings** — scoring configuration, LLM provider/model, cost assumptions, and local data status.

## Design issues resolved

1. **Current values versus historical tracking:** current fields live on `books`; every later refresh can append a `market_snapshot`.
2. **Aggregates versus traceability:** pain-point/praise rows are derived indexes; joins retain every supporting review and extraction payload.
3. **Automated versus human scores:** score snapshots preserve automated components and separate overrides.
4. **LLM reproducibility versus evolving prompts:** the cache key includes review content hash, provider/model, schema version, and prompt version; analysis runs remain immutable.
5. **CSV book matching:** V1 requires an unambiguous source identifier for review imports; title-only fuzzy matching reports an error instead of silently attaching evidence to the wrong book.
6. **Sentiment versus market insight:** sentiment is only one review field. Problems, desired outcomes, praise, reader level, severity, and content-solvability are first-class structured data.
7. **Sparse data:** scores may be calculated, but recommendation labels are confidence-gated.
8. **Changing economics:** royalty, print-cost, and model-cost assumptions are configuration values with an effective date, never hidden constants.

## Implementation phases

### Phase 1 — foundation

Architecture, normalized database, repositories, synthetic scenarios, basic scoring primitives, Streamlit navigation/dashboard, and smoke tests.

### Phase 2 — ingestion and browsing

Manual book entry, validated CSV/JSON imports with row-level reports, competitor summaries, review cleaning/deduplication, and review browser.

### Phase 3 — evidence extraction

Pydantic review schema, mock/OpenAI providers, batching/cache/cost capture, complaint and praise extraction, canonical clustering, and evidence drill-down.

### Phase 4 — decisions

Full component scoring, confidence, UDI, human overrides, explanations, warnings, and recommendation labels.

### Phase 5 — outputs and workflow

Opportunity report, evidence-grounded book concept, comparison, pipeline controls, and CSV/JSON/Markdown exports.

### Phase 6 — hardening

Broader tests, malformed-input UX, migration support, structured logging, performance checks, README completion, and UI polish.

## Deliberately not automated in V1

- Amazon search, page scraping, CAPTCHA/rate-limit/bot-detection bypass, or sales estimation.
- Keyword volume, BSR-to-sales conversion, trend alerts, and scheduled refreshes.
- Automatic publish/reject decisions.
- Fully automatic semantic cluster merging without review and override.
- Fact verification, medical/legal/financial approval, cover scoring, or book generation.
- Authentication, multi-user workflows, cloud deployment, and ad integrations.

## Assumptions

- One trusted local user and one SQLite database.
- The user has the right to import and analyze supplied data.
- Source identifiers are preferred; ASIN is metadata, not fabricated when absent.
- English review analysis is the initial target, but source text is stored as Unicode.
- Scores guide deeper validation and never assert expected sales.
- Python 3.12 is the target; the code may work on compatible recent Python 3 versions.

