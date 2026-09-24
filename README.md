# KDP Opportunity Finder

KDP Opportunity Finder is a local, evidence-first decision-support application for researching nonfiction publishing niches. It combines user-supplied market observations with review-derived customer gaps, competition, economics, production suitability, expansion potential, and a separate evidence-confidence score.

V1 is complete. It does not scrape Amazon, predict sales, generate finished books, or make automatic publishing decisions. Missing observations stay missing, derived findings retain their source links, and human adjustments never overwrite automated evidence.

## What V1 includes

- Manual, CSV, and JSON entry for competitor books and review evidence.
- Preview-before-import validation, row-level rejection reasons, provenance, and duplicate detection.
- Deterministic local review analysis plus an optional OpenAI Structured Outputs provider.
- Traceable pain-point and praise clustering with review-level drill-down and human corrections.
- Six inspectable opportunity components, confidence warnings, the Unmet Demand Index, and confidence-gated recommendations.
- Immutable score snapshots and separately recorded human decision adjustments.
- Evidence-linked opportunity reports and evidence-grounded book-specification drafts.
- Side-by-side niche comparison, a manual workflow pipeline, and traceable CSV/JSON exports.
- Alembic-managed schema startup, structured local logs, bounded processing, responsive Streamlit pages, and a 90-test regression suite.

## Requirements

- Windows PowerShell.
- Python 3.12. The verified development environment uses Python 3.12.14.
- A writable local project directory.
- No API key for the default deterministic mock-analysis workflow.

The current interface requires Streamlit 1.63 or newer. Install the declared dependencies rather than relying on globally installed packages.

## Quick start

From the repository root, first confirm that `python --version` reports Python 3.12. If `python` is not on PATH, use the full path to a Python 3.12 `python.exe`; the equivalent creation command is `& "C:\Path\To\Python312\python.exe" -m venv .venv`.

Then run:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item -LiteralPath .\.env.example -Destination .\.env
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Using the virtual-environment interpreter in every later command avoids PATH, launcher, and activation ambiguity.

Open the local URL printed by Streamlit, normally `http://localhost:8501`. The `.env` copy is optional when the defaults are acceptable.

On startup, the app safely upgrades an empty or versioned database to the current Alembic revision. A legacy unversioned database is stamped only when its schema exactly matches the reviewed baseline. Back up existing research before schema work and follow [MIGRATIONS.md](MIGRATIONS.md).

## First-use choices

For a guided demonstration, select **Load synthetic sample** in the sidebar. It creates three deliberately different scenarios with 30 books and 180 original synthetic reviews. It never replaces a database that already contains research.

For real research:

1. Open **Research** and create a niche hypothesis.
2. Add competitor books manually or import them from CSV/JSON.
3. Import reviews using the exact book source identifiers from step 2.
4. Run **Analyze reviews** with the local mock provider or the optional OpenAI provider.
5. Use **Niche detail** to inspect competitors, source reviews, pain points, praise, run history, and decision evidence.
6. Calculate a score snapshot, review its confidence and missing observations, then use reports, specifications, comparison, pipeline, and exports as decision aids.

The complete field contract, examples, matching rules, and rejection behavior are in [IMPORT_REFERENCE.md](IMPORT_REFERENCE.md). Downloadable CSV and JSON examples are also available inside the Research page.

## Application pages

| Page | Purpose |
|---|---|
| **Dashboard** | Corpus totals, ranked scored niches, confidence warnings, stage counts, and recent analysis runs. |
| **Research** | Create niches, add/edit books, preview and persist imports, and run review analysis. |
| **Niche detail** | Inspect competitor data, source reviews, derived evidence, score explanations, warnings, adjustments, and history. |
| **Opportunity report** | Preview and download a deterministic Markdown report linked to an immutable score snapshot and supporting evidence IDs. |
| **Book specification** | Generate an append-only planning draft whose choices are labeled as evidence-backed, assumptions, or risk-review requirements. |
| **Compare** | Compare two to six niches while keeping scores, confidence, UDI, warnings, and evidence coverage separate. |
| **Pipeline** | Apply manual workflow statuses with required rationales and append-only transition history. |
| **Exports** | Download explicitly scoped decision, book, or review data as CSV or JSON with provenance and missing values preserved. |
| **Settings** | Inspect local configuration, the configured provider/model, score weights, and scoring-policy location. |

## Review analysis providers

The default `mock` provider is deterministic, local, and free to run. It is intended for testing the complete evidence workflow without credentials. Unchanged reviews reuse cached extraction results; **Force reanalysis** deliberately bypasses that cache.

To use the optional OpenAI provider, set these values in `.env` and select **OpenAI · API** in Research:

```dotenv
OPENAI_API_KEY=your-api-key
OPENAI_MODEL=gpt-4.1-mini
```

API execution is optional and can incur separate usage charges. Token totals are stored for each run. Cost estimates stay blank unless you enter verified input/output prices in `.env`; the repository does not hard-code prices that may become stale. Provider failures create a failed run record without replacing the last accepted evidence.

## Decisions and evidence boundaries

All six component scores use a 0–100 scale. A higher competition component means the environment appears more accessible. Confidence is calculated and displayed separately from the opportunity score; low confidence gates recommendation language to **Needs more data**.

The Unmet Demand Index is a diagnostic product of demand, gap strength, solvability, and competitive accessibility. It is not a sales estimate. Every score snapshot retains its policy version, weights, inputs, formulas, missing observations, and warnings.

A human adjustment requires a rationale and creates another snapshot. It does not change the automated component values, automated total, confidence, or earlier history. Pipeline status is also manual and never changes automatically because of a score.

## Data and configuration

| Item | Default or location |
|---|---|
| SQLite database | `kdp_opportunity_finder.db` |
| Database override | `KDP_DATABASE_URL` in `.env` |
| LLM provider | `KDP_LLM_PROVIDER=mock` |
| Review batch size | `KDP_LLM_BATCH_SIZE=20`, clamped to 1–50 |
| Scoring policy | `config/scoring.yaml` |
| Structured log | `logs/kdp_opportunity_finder.jsonl` |
| Log controls | `KDP_LOG_PATH` and `KDP_LOG_LEVEL` |

The database, `.env`, logs, exports, backups, virtual environment, and Streamlit secrets are ignored by Git. Keep independent backups of research you cannot recreate.

When an operation fails, the UI shows recovery guidance and a short reference instead of raw exception text. Match that reference to the local JSON-lines log. Structured failure records retain safe identifiers, exception classes, and traceback locations while excluding exception messages, API keys, authorization values, and review/body content.

## Verification

Run the complete regression suite and compilation check from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall -q analysis app_pages collectors config db llm migrations models sample_data services tests ui app.py
git diff --check
```

Run the disposable representative-data performance profile with:

```powershell
.\.venv\Scripts\python.exe scripts\profile_performance.py --repeats 5
```

The profile creates a temporary migrated database, exercises representative workflows, reports query counts and local timings, and removes the temporary database afterward.

## Documentation map

- [IMPORT_REFERENCE.md](IMPORT_REFERENCE.md) — accepted CSV/JSON shapes, fields, aliases, matching, validation, and examples.
- [ARCHITECTURE.md](ARCHITECTURE.md) — product boundary, modules, data model, scoring design, and V1 decisions.
- [MIGRATIONS.md](MIGRATIONS.md) — backup, schema inspection, upgrade, revision creation, and recovery procedures.
- [TEST_MATRIX.md](TEST_MATRIX.md) — critical-business-rule coverage, protected invariants, and residual risks.
- [PERFORMANCE.md](PERFORMANCE.md) — representative measurements, explicit processing bounds, and freshness behavior.
- [ROADMAP.md](ROADMAP.md) — V1 limitations and candidate post-V1 directions.
- [KANBAN.md](KANBAN.md) — completed execution history and current project status.

## Limitations

- All marketplace observations and review text must be supplied by the user from sources they are permitted to use. V1 has no Amazon collector or scraper.
- Scores compare stored observations under an explicit policy; they do not estimate demand volume, unit sales, royalties, profit, or future performance.
- The deterministic mock provider proves the workflow but is not a substitute for expert qualitative research. OpenAI output can also be incomplete or wrong and must be reviewed against source evidence.
- English-language review analysis is the initial target. Unicode source text is retained, but multilingual extraction quality is not established.
- The app assumes one trusted local user and one SQLite database. It has no authentication, cloud deployment, multi-user editing, or multi-process write guarantees.
- Reports and specifications are research artifacts, not finished manuscripts, professional advice, rights clearance, or automatic publish/reject decisions.
- Scheduled collection, alerts, trend tracking, cover analysis, ad integrations, and automated book production are outside V1.

See [ROADMAP.md](ROADMAP.md) for the boundary between completed V1 behavior and possible future work. A roadmap item is not a promise or verified marketplace capability until it is explicitly moved onto the Kanban board.
