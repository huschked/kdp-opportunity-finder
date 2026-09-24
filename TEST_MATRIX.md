# V1 Critical Business Logic Test Matrix

Last updated: 2026-09-24

This matrix maps the V1 business rules to automated regression evidence. It tracks requirements coverage, not line coverage. The suite remains intentionally local; a disposable performance profile and representative desktop/mobile browser checks supplement the automated tests. External OpenAI requests, operating-system failures, concurrency, and unprofiled large-volume behavior remain residual risks.

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
| Database migrations | Fresh databases upgrade to Alembic head; matching populated databases retain their records when adopted | Version state, exact metadata agreement, and idempotent startup are covered | Partial or unexpected unversioned schemas are refused without adding the version table or changing stored rows | `tests/test_migrations.py` |
| Operational failures | Expected and unexpected operations produce structured diagnostics plus a short UI reference | Only allow-listed identifiers enter log context; secrets and review/body fields are redacted | Raw exception text is withheld from the UI and structured failure record; failed transactions and incompatible schemas retain prior data | `tests/test_error_handling.py`, `tests/test_analysis_service.py` |
| Performance boundaries | Representative reads, imports, scoring, exports, and analysis complete on a disposable synthetic corpus | Latest-row queries remain bounded by parent count; import lookups and provider batches have explicit caps; cached reviews make zero provider calls | New review content invalidates only its extraction cache, and database results are not cached across mutations | `tests/test_performance.py`, `scripts/profile_performance.py` |
| Streamlit application | Seeded workflows execute across every top-level page through the real entry point | Data-dependent pages render actionable empty states; provider selection and responsive native controls retain explicit labels | Every interaction rerun is checked for uncaught exceptions; rendered desktop/mobile checks found no page-level horizontal overflow | `tests/test_streamlit_app.py`, manual browser verification |
| Documentation contract | Root documentation links resolve and shipped CSV/JSON templates validate against the current schemas | Every current book/review import field and accepted alias is present in the import reference | Missing linked files, undocumented schema fields, or invalid templates fail the suite | `tests/test_documentation.py` |

## Guardrail-to-test traceability

| Guardrail | Regression evidence |
|---|---|
| No fabricated missing values | `test_competitor_summary_ignores_missing_values`, `test_every_component_is_inspectable_and_bounded`, `test_decision_export_uses_latest_snapshot_and_keeps_uncertainty_separate`, `test_book_export_filters_one_niche_and_preserves_source_and_market_snapshot_ids` |
| Evidence provenance | `test_book_csv_import_is_partial_and_preserves_report`, `test_analysis_pipeline_persists_evidence_excludes_logistics_and_reuses_cache`, `test_report_snapshots_cover_all_three_synthetic_scenarios`, `test_review_export_preserves_raw_evidence_analysis_and_derived_link_ids` |
| Immutable history | `test_manual_book_edits_append_market_snapshots`, `test_score_snapshot_preserves_explanations_weights_and_human_override`, `test_specification_history_is_append_only`, `test_status_change_persists_and_appends_auditable_history` |
| Human control remains explicit | `test_human_override_rejects_invalid_values_without_appending_snapshot`, `test_status_change_rejects_invalid_noop_or_unexplained_transitions`, `test_human_merge_rejects_cross_niche_groups_without_deleting_evidence` |
| Failure atomicity | `test_duplicate_source_identifier_does_not_mutate_book_or_append_snapshot`, `test_fully_rejected_import_records_failed_batch_without_creating_books`, `test_provider_failure_records_failed_run_without_replacing_current_analysis`, `test_partial_unversioned_database_is_refused_without_schema_changes`, `test_failed_transaction_rolls_back_without_creating_a_record` |
| Cross-niche isolation | `test_book_import_accepts_matching_niche_column_and_rejects_mismatch`, `test_human_merge_rejects_cross_niche_groups_without_deleting_evidence`, `test_report_rejects_snapshot_from_another_niche`, `test_comparison_rejects_unknown_niche_ids` |
| Sensitive diagnostic data | `test_structured_failure_log_keeps_context_and_redacts_sensitive_values`, `test_streamlit_error_is_recovery_oriented_and_hides_raw_exception` |

## Inventory

The suite currently collects 90 cases:

| Test module | Cases |
|---|---:|
| `test_analysis_service.py` | 8 |
| `test_book_service.py` | 3 |
| `test_comparison_service.py` | 4 |
| `test_concept_service.py` | 6 |
| `test_database.py` | 3 |
| `test_decision_scoring.py` | 5 |
| `test_documentation.py` | 3 |
| `test_export_service.py` | 4 |
| `test_error_handling.py` | 5 |
| `test_import_service.py` | 6 |
| `test_market.py` | 1 |
| `test_migrations.py` | 3 |
| `test_niche_service.py` | 4 |
| `test_openai_provider.py` | 2 |
| `test_performance.py` | 5 |
| `test_pipeline_service.py` | 7 |
| `test_report_service.py` | 6 |
| `test_review_cleaning.py` | 1 |
| `test_sample_data.py` | 2 |
| `test_scoring.py` | 5 |
| `test_scoring_service.py` | 5 |
| `test_streamlit_app.py` | 2 |
| **Total** | **90** |

## Residual V1 risks and deliberate boundaries

- **Live provider behavior:** the OpenAI adapter is contract-tested with a fake client, but no test spends API credits or depends on live network availability.
- **Rendered-browser behavior:** `AppTest` verifies page execution and widget state, and representative 1440×900 and 390×844 browser checks cover layout and page-level overflow. Keyboard-only flow, screen-reader output, file transfer in every browser, and formal accessibility certification remain manual.
- **Schema and concurrency:** migrations cover fresh upgrades, populated current-schema adoption, exact schema comparison, version state, idempotent startup, and incompatible-schema refusal. Multi-process concurrent writes remain outside the single-user SQLite V1 model.
- **Scale:** query counts and bounded batch behavior are covered on focused tests and a 3-niche/30-book/180-review profile. Much larger corpora, memory pressure, and long-running provider latency require separate capacity testing.
- **Operational environment:** structured failure handling is covered locally. Filesystem exhaustion, OS-level permission changes after startup, and external log aggregation remain outside the local V1 scope.
- **Input rights and representativeness:** the app preserves provenance but cannot establish whether user-supplied observations are licensed, current, complete, or representative of a marketplace.

## Verification commands

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall -q analysis app_pages collectors config db llm migrations models sample_data services tests ui app.py
git diff --check
```
