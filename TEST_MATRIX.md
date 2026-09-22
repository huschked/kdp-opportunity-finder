# V1 Critical Business Logic Test Matrix

Last updated: 2026-09-21

This matrix maps the V1 business rules to automated regression evidence. It tracks requirements coverage, not line coverage. The suite remains intentionally local: external OpenAI requests, browser rendering details, concurrency, and large-volume performance are listed separately as residual risks.

## Protected invariants

1. Missing marketplace observations remain missing; the application does not invent sales, demand, rank, price, or profitability data.
2. Derived findings retain stable links to stored sources, records, analyses, and immutable snapshots.
3. Automated scores, human adjustments, confidence, warnings, and workflow status remain separate.
4. Human-controlled changes require explicit input and do not silently overwrite automated evidence.
5. Failed validation or provider work does not partially replace accepted evidence.

## Coverage matrix

| Area | Happy path | Boundary and uncertainty | Failure and guardrail | Automated evidence |
|---|---|---|---|---|
| Niche creation | Creates and normalizes a valid niche | Whitespace is normalized | Missing fields and duplicate names are rejected without losing the existing record | `tests/test_niche_service.py` |
| Manual competitor books | Creates and edits a book with append-only market snapshots | Nullable marketplace fields remain allowed | Missing niches and duplicate source identifiers do not create or mutate records | `tests/test_book_service.py` |
| CSV/JSON imports | Valid rows persist with source and batch provenance | Partial batches, duplicate review text, niche matching, JSON object roots, and normalization are covered | Malformed, unsupported, non-UTF-8, unknown-book, and fully rejected inputs produce issues or failed batches without fabricated records | `tests/test_import_service.py`, `tests/test_review_cleaning.py` |
| Review analysis | Deterministic analysis persists review analyses, pain, praise, run metadata, and cache reuse | Mixed sentiment and excluded logistics evidence remain auditable; human rename/merge survives reanalysis | Empty corpora, provider failures, schema violations, and cross-niche merges are rejected without replacing current evidence | `tests/test_analysis_service.py`, `tests/test_openai_provider.py` |
| Decision scoring | Six components, overall score, UDI, policy, explanations, and snapshots are persisted | Missing observations, sparse/concentrated samples, score bounds, and three synthetic markets are covered | Invalid weights/components and invalid or premature human overrides are rejected without appending snapshots | `tests/test_scoring.py`, `tests/test_decision_scoring.py`, `tests/test_scoring_service.py` |
| Confidence gating | Confidence inputs and warnings are inspectable | Low confidence gates high automated or human scores to “Needs more data” | Missing and concentrated evidence cannot silently become a strong recommendation | `tests/test_scoring.py`, `tests/test_decision_scoring.py`, `tests/test_comparison_service.py` |
| Opportunity reports | Reports cite score, book, pain, praise, and review evidence across all sample markets | Sparse evidence and corpus/analysis staleness remain prominent | Missing, legacy, or cross-niche score snapshots are rejected | `tests/test_report_service.py` |
| Book specifications | Evidence-backed design choices cite accepted evidence and append history | Sparse evidence becomes labeled assumptions; regulated topics require explicit expert review | Uncited claims disguised as evidence and generation without a score snapshot are rejected | `tests/test_concept_service.py` |
| Niche comparison | Latest decision snapshots rank scored niches while preserving automated and human values | Unscored niches remain visible; unequal confidence and coverage produce warnings | Unknown niche identifiers are rejected | `tests/test_comparison_service.py` |
| Workflow pipeline | Manual transitions persist an append-only rationale history | Every stage, filtering, zero counts, and score/status separation are covered | Invalid, no-op, unexplained, unknown-niche, and invalid-history requests are rejected | `tests/test_pipeline_service.py` |
| CSV/JSON exports | Decision, book, and review datasets serialize with stable provenance IDs | Latest-snapshot policy, filtering, nested evidence, CSV blanks, and JSON nulls are covered | Unsupported datasets, missing required scope, and unknown niches are rejected | `tests/test_export_service.py` |
| Streamlit application | Seeded workflows execute across every top-level page through the real entry point | Data-dependent pages render safe empty states before sample data exists | Every interaction rerun is checked for uncaught exceptions | `tests/test_streamlit_app.py` |

## Guardrail-to-test traceability

| Guardrail | Regression evidence |
|---|---|
| No fabricated missing values | `test_competitor_summary_ignores_missing_values`, `test_every_component_is_inspectable_and_bounded`, `test_decision_export_uses_latest_snapshot_and_keeps_uncertainty_separate`, `test_book_export_filters_one_niche_and_preserves_source_and_market_snapshot_ids` |
| Evidence provenance | `test_book_csv_import_is_partial_and_preserves_report`, `test_analysis_pipeline_persists_evidence_excludes_logistics_and_reuses_cache`, `test_report_snapshots_cover_all_three_synthetic_scenarios`, `test_review_export_preserves_raw_evidence_analysis_and_derived_link_ids` |
| Immutable history | `test_manual_book_edits_append_market_snapshots`, `test_score_snapshot_preserves_explanations_weights_and_human_override`, `test_specification_history_is_append_only`, `test_status_change_persists_and_appends_auditable_history` |
| Human control remains explicit | `test_human_override_rejects_invalid_values_without_appending_snapshot`, `test_status_change_rejects_invalid_noop_or_unexplained_transitions`, `test_human_merge_rejects_cross_niche_groups_without_deleting_evidence` |
| Failure atomicity | `test_duplicate_source_identifier_does_not_mutate_book_or_append_snapshot`, `test_fully_rejected_import_records_failed_batch_without_creating_books`, `test_provider_failure_records_failed_run_without_replacing_current_analysis` |
| Cross-niche isolation | `test_book_import_accepts_matching_niche_column_and_rejects_mismatch`, `test_human_merge_rejects_cross_niche_groups_without_deleting_evidence`, `test_report_rejects_snapshot_from_another_niche`, `test_comparison_rejects_unknown_niche_ids` |

## Inventory

The suite currently collects 73 cases:

| Test module | Cases |
|---|---:|
| `test_analysis_service.py` | 8 |
| `test_book_service.py` | 3 |
| `test_comparison_service.py` | 4 |
| `test_concept_service.py` | 6 |
| `test_database.py` | 3 |
| `test_decision_scoring.py` | 5 |
| `test_export_service.py` | 4 |
| `test_import_service.py` | 6 |
| `test_market.py` | 1 |
| `test_niche_service.py` | 4 |
| `test_openai_provider.py` | 2 |
| `test_pipeline_service.py` | 7 |
| `test_report_service.py` | 6 |
| `test_review_cleaning.py` | 1 |
| `test_sample_data.py` | 2 |
| `test_scoring.py` | 5 |
| `test_scoring_service.py` | 5 |
| `test_streamlit_app.py` | 1 |
| **Total** | **73** |

## Residual risks and later Phase 6 work

- **Live provider behavior:** the OpenAI adapter is contract-tested with a fake client, but no test spends API credits or depends on live network availability.
- **Rendered-browser behavior:** `AppTest` verifies page execution and widget state; actual file-transfer behavior, responsive layout, keyboard navigation, and screen-reader output remain for `P6-UI-01`.
- **Schema evolution and concurrency:** tests use fresh SQLite schemas. Upgrade paths for existing databases and concurrent writes remain for `P6-MIGRATE-01`.
- **Scale:** correctness is covered on focused and synthetic corpora. Query counts, large imports, memory use, and rerun latency remain for `P6-PERF-01`.
- **Operational diagnostics:** provider failures are persisted, but consistent structured logs and user-facing recovery messages remain for `P6-ERROR-01`.

## Verification commands

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall -q analysis app_pages collectors config db llm models sample_data services tests ui app.py
git diff --check
```
