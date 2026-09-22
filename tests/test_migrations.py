from __future__ import annotations

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
import pytest
from sqlalchemy import func, inspect, select, text
from sqlalchemy.orm import Session

from db.database import build_engine, initialize_database
from db.migrations import (
    SchemaStateError,
    expected_schema,
    metadata_differences,
    reflected_schema,
    schema_differences,
)
from models import Base, Book, Niche, Review, ScoreSnapshot
from sample_data.generate import seed_sample_data


HEAD_REVISION = "20260921_0001"


def test_fresh_database_upgrades_to_head_and_matches_metadata(tmp_path) -> None:
    database_path = tmp_path / "fresh.db"
    engine = build_engine(f"sqlite:///{database_path.as_posix()}")

    created = initialize_database(engine)
    current = initialize_database(engine)

    assert created.action == "created"
    assert created.current_revision == HEAD_REVISION
    assert current.action == "current"
    assert current.previous_revision == HEAD_REVISION
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == HEAD_REVISION
        assert reflected_schema(connection) == expected_schema()
        assert schema_differences(reflected_schema(connection)) == ()
        context = MigrationContext.configure(connection)
        assert compare_metadata(context, Base.metadata) == []


def test_current_unversioned_database_is_stamped_without_losing_data(tmp_path) -> None:
    database_path = tmp_path / "legacy-current.db"
    engine = build_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        assert seed_sample_data(session) is True
        before = {
            "niches": session.scalar(select(func.count(Niche.id))),
            "books": session.scalar(select(func.count(Book.id))),
            "reviews": session.scalar(select(func.count(Review.id))),
            "scores": session.scalar(select(func.count(ScoreSnapshot.id))),
        }
    assert "alembic_version" not in inspect(engine).get_table_names()
    with engine.connect() as connection:
        assert metadata_differences(connection) == ()

    result = initialize_database(engine)

    assert result.action == "stamped"
    assert result.previous_revision is None
    assert result.current_revision == HEAD_REVISION
    with Session(engine) as session:
        after = {
            "niches": session.scalar(select(func.count(Niche.id))),
            "books": session.scalar(select(func.count(Book.id))),
            "reviews": session.scalar(select(func.count(Review.id))),
            "scores": session.scalar(select(func.count(ScoreSnapshot.id))),
        }
        assert after == before
        assert session.scalar(select(Niche.name).order_by(Niche.id)) == "Home Coffee Roasting"


def test_partial_unversioned_database_is_refused_without_schema_changes(tmp_path) -> None:
    database_path = tmp_path / "partial.db"
    engine = build_engine(f"sqlite:///{database_path.as_posix()}")
    Niche.__table__.create(engine)
    with Session(engine) as session:
        niche = Niche(name="Preserve me", seed_keyword="preserve")
        session.add(niche)
        session.commit()
        niche_id = niche.id

    with pytest.raises(SchemaStateError, match="does not match the reviewed baseline"):
        initialize_database(engine)

    assert "alembic_version" not in inspect(engine).get_table_names()
    with Session(engine) as session:
        assert session.get(Niche, niche_id).name == "Preserve me"
