# Database migrations

KDP Opportunity Finder uses Alembic for every schema change. The default SQLite database contains local research evidence, so schema work must preserve the database file and its records.

## Startup behavior

`app.py` checks the schema before rendering any page:

- An empty database is upgraded through every Alembic revision to `head`.
- An existing unversioned database is stamped only when its tables, columns, types, indexes, and constraints match the reviewed baseline.
- A versioned database behind `head` is upgraded in revision order.
- An unversioned database with a partial or unexpected schema is refused without applying schema changes. Back it up and inspect the reported differences instead of recreating it.

The current baseline revision is `20260921_0001`. Stamping records that a matching schema is already at this revision; it does not recreate tables or rewrite application rows.

## Back up before changing schema

Stop Streamlit before copying the database so no write is in progress. From the project root:

```powershell
New-Item -ItemType Directory -Path .\backups -Force
Copy-Item -LiteralPath .\kdp_opportunity_finder.db -Destination .\backups\kdp_opportunity_finder-before-migration.db
Get-FileHash -Algorithm SHA256 .\kdp_opportunity_finder.db, .\backups\kdp_opportunity_finder-before-migration.db
```

Confirm both hashes match. Database backups under `backups/` are deliberately ignored by Git and remain local.

## Inspect and apply migrations

Use the project virtual environment from the repository root:

```powershell
.\.venv\Scripts\python.exe -m alembic current --check-heads
.\.venv\Scripts\python.exe -m alembic history
.\.venv\Scripts\python.exe -m alembic upgrade head
```

The app performs the same safe upgrade on startup. To run that application bootstrap directly and see whether it created, stamped, upgraded, or confirmed the database:

```powershell
.\.venv\Scripts\python.exe -m db.migrations
```

Set `KDP_DATABASE_URL` before these commands when working with a database other than the project default.

## Create a schema revision

1. Change the SQLAlchemy models.
2. Generate a candidate revision:

   ```powershell
   .\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "describe the schema change"
   ```

3. Review every generated `upgrade()` and `downgrade()` operation. Autogeneration is a candidate, not approval. Check renames, nullability, defaults, foreign keys, indexes, and any required data transition explicitly.
4. Run the migration tests against temporary databases, then exercise a disposable copy of a populated database.
5. Run the full regression suite before committing the revision.

Never use `Base.metadata.create_all()` as an upgrade mechanism. It cannot review or sequence changes to existing tables.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_migrations.py
.\.venv\Scripts\python.exe -m pytest -q
git diff --check
```

The migration tests create only temporary databases. They verify a fresh upgrade, non-destructive adoption of a populated current-schema database, exact metadata agreement, version state, idempotent startup, and refusal of an incompatible unversioned database.

## Recovery boundary

Do not use `alembic downgrade base` on a database that contains research data; the baseline downgrade removes all application tables. If an upgrade fails:

1. Stop the app and keep the failed database unchanged for diagnosis.
2. Record the error and run `alembic current` against that file.
3. Fix the migration and test the fix on a copy.
4. Only after confirming the backup hash and selecting the exact files, restore the verified backup over the default database.

If the database cannot be opened or its schema no longer matches a known revision, preserve both the failed file and the backup and diagnose them before any overwrite.
