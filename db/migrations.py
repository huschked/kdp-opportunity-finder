"""Safe Alembic bootstrap and upgrade workflow for local databases."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, inspect
from sqlalchemy.engine import Connection

from models import Base


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_CONFIG_PATH = PROJECT_ROOT / "alembic.ini"
VERSION_TABLE = "alembic_version"


class SchemaStateError(RuntimeError):
    """Raised when an unversioned database is not the reviewed baseline schema."""


@dataclass(frozen=True, slots=True)
class MigrationResult:
    action: str
    previous_revision: str | None
    current_revision: str


def migration_config(*, database_url: str | None = None) -> Config:
    config = Config(str(ALEMBIC_CONFIG_PATH))
    config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    if database_url is not None:
        config.set_main_option("sqlalchemy.url", database_url)
    return config


def expected_schema() -> dict[str, tuple[str, ...]]:
    return {
        table_name: tuple(column.name for column in table.columns)
        for table_name, table in sorted(Base.metadata.tables.items())
    }


def reflected_schema(connection: Connection) -> dict[str, tuple[str, ...]]:
    inspector = inspect(connection)
    return {
        table_name: tuple(column["name"] for column in inspector.get_columns(table_name))
        for table_name in sorted(inspector.get_table_names())
        if table_name != VERSION_TABLE
    }


def schema_differences(
    actual: Mapping[str, tuple[str, ...]],
    expected: Mapping[str, tuple[str, ...]] | None = None,
) -> tuple[str, ...]:
    expected = expected or expected_schema()
    differences: list[str] = []
    missing_tables = sorted(set(expected) - set(actual))
    extra_tables = sorted(set(actual) - set(expected))
    if missing_tables:
        differences.append("missing tables: " + ", ".join(missing_tables))
    if extra_tables:
        differences.append("unexpected tables: " + ", ".join(extra_tables))
    for table_name in sorted(set(expected) & set(actual)):
        missing_columns = sorted(set(expected[table_name]) - set(actual[table_name]))
        extra_columns = sorted(set(actual[table_name]) - set(expected[table_name]))
        if missing_columns:
            differences.append(
                f"{table_name} missing columns: {', '.join(missing_columns)}"
            )
        if extra_columns:
            differences.append(
                f"{table_name} has unexpected columns: {', '.join(extra_columns)}"
            )
    return tuple(differences)


def metadata_differences(connection: Connection) -> tuple[str, ...]:
    """Return Alembic's detailed schema diff for safe baseline adoption."""

    context = MigrationContext.configure(
        connection,
        opts={"compare_type": True},
    )
    differences = compare_metadata(context, Base.metadata)
    return tuple(repr(difference) for difference in differences)


def _current_revision(connection: Connection) -> str | None:
    return MigrationContext.configure(connection).get_current_revision()


def _head_revision(config: Config) -> str:
    head = ScriptDirectory.from_config(config).get_current_head()
    if head is None:
        raise RuntimeError("The migration environment has no head revision")
    return head


def _run_command(engine: Engine, operation: object, revision: str) -> None:
    config = migration_config(database_url=str(engine.url))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        operation(config, revision)  # type: ignore[operator]


def ensure_database_schema(engine: Engine) -> MigrationResult:
    """Upgrade a versioned database or safely adopt the reviewed current schema."""

    config = migration_config(database_url=str(engine.url))
    head = _head_revision(config)
    with engine.connect() as connection:
        table_names = set(inspect(connection).get_table_names())
        previous_revision = _current_revision(connection) if VERSION_TABLE in table_names else None

    if not table_names:
        _run_command(engine, command.upgrade, "head")
        return MigrationResult("created", previous_revision, head)

    if VERSION_TABLE not in table_names:
        with engine.connect() as connection:
            differences = (
                *schema_differences(reflected_schema(connection)),
                *metadata_differences(connection),
            )
        if differences:
            details = "; ".join(differences)
            raise SchemaStateError(
                "The database is unversioned and does not match the reviewed baseline. "
                f"No schema changes were made. Differences: {details}. "
                "Back up the database and follow MIGRATIONS.md before continuing."
            )
        _run_command(engine, command.stamp, "head")
        return MigrationResult("stamped", previous_revision, head)

    if previous_revision == head:
        return MigrationResult("current", previous_revision, head)

    _run_command(engine, command.upgrade, "head")
    with engine.connect() as connection:
        current_revision = _current_revision(connection)
    if current_revision != head:
        raise RuntimeError(
            f"Database migration ended at {current_revision or 'no revision'}, expected {head}"
        )
    return MigrationResult("upgraded", previous_revision, head)


if __name__ == "__main__":
    from db.database import ENGINE

    result = ensure_database_schema(ENGINE)
    print(
        f"Database migration action={result.action} "
        f"previous={result.previous_revision or 'none'} current={result.current_revision}"
    )
