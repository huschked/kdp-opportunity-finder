# Performance verification

`P6-PERF-01` focuses on bounded local work without weakening evidence totals, provenance, or cache invalidation.

## Repeat the profile

Run the disposable synthetic-data profile from the repository root:

```powershell
.venv\Scripts\python.exe scripts\profile_performance.py --repeats 5
```

The script creates a temporary migrated SQLite database, loads the deterministic 3-niche/30-book/180-review sample, exercises every major workflow, prints median wall time and SQL-statement counts, and removes the database afterward. Timings are machine-dependent; statement counts and returned record totals are the primary regression signals.

## Before and after

These measurements were captured on 2026-09-23 on the same local machine. The before run used the pre-story implementation. The after run used the command above. Small timing changes should not be treated as a benchmark guarantee.

| Representative flow | Before SQL | After SQL | Before median | After median | Change |
|---|---:|---:|---:|---:|---|
| Dashboard | 7 | 4 | 4.3 ms | 3.9 ms | Four separate total-count reads became one statement. |
| Niche competitor view setup | 2 | 1 | 1.5 ms | 0.9 ms | Removed the duplicate book query and only loads data for the selected view. |
| Niche review view setup | 5 | 4 | 5.7 ms | 4.7 ms | Removed the unrelated competitor query and narrowed filter-option columns. |
| Comparison | 2 | 2 | 1.6 ms | 3.1 ms | Same query count; SQL now returns one latest snapshot per niche instead of all history. |
| Pipeline page | 5 | 3 | 3.7 ms | 2.7 ms | Filters reuse the loaded snapshot; filter widgets submit as one form. |

The final representative profile also recorded:

| Flow | SQL statements | Median/result |
|---|---:|---|
| Book export | 3 | 3.2 ms / 10 records |
| Review export | 4 | 5.9 ms / 60 records |
| Decision export | 4 | 4.3 ms / 3 records |
| Book import preview | 2 | 1.4 ms / 1 accepted record |
| Scoring | 7 | 17.3 ms / exact score retained |
| Full 60-review mock analysis | 241 | 116.0 ms / 60 analyzed |
| Fully cached 60-review analysis | 6 | 24.7 ms / 60 cached |

The analysis statement total includes its intentionally auditable run, evidence-link, and aggregate writes. The important cached-run boundary is that an unchanged corpus now makes zero extraction or clustering provider calls; adding or changing a review invalidates only that review's extraction before deterministic re-clustering.

## Explicit bounds and freshness rules

- Latest score and market snapshots are selected in SQL with deterministic `timestamp DESC, id DESC` tie-breaking. Score or market history depth no longer increases the number of ORM snapshot objects returned to comparison, pipeline, dashboard, or book export flows.
- Analysis extraction batches are capped at 50 reviews. A requested larger batch is reduced to 50, and the last batch contains the deterministic remainder.
- Import duplicate lookups query only uploaded candidate keys in batches of 400 pairs. They do not load every stored book identifier or review hash into memory.
- Pipeline search/status widgets are in a form, so typing and multiselect changes do not rerun the page until **Apply filters** is selected. Filtering then reuses the already loaded snapshot without another query.
- No cross-rerun database cache was added. Database mutations therefore cannot leave dashboard, score, comparison, pipeline, export, or import results stale.
- Exports intentionally contain every record in their stated scope. The 100-row Streamlit preview remains only a visible preview; CSV/JSON downloads and manifest totals are not truncated.

## Regression coverage

`tests/test_performance.py` protects:

- the single-statement dashboard totals aggregate;
- one-row-per-parent latest score and market queries at 25 historical snapshots per parent, including timestamp ties;
- query-free filtering of an already-loaded pipeline snapshot;
- the 400-pair import lookup boundary; and
- the 50-review analysis batch cap, zero-call cached path, and new-content invalidation.
