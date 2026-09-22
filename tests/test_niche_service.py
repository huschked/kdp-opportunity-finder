from __future__ import annotations

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from models import Base, Niche
from services.niche_service import NicheNameConflict, NicheService


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_niche_creation_normalizes_user_text() -> None:
    with _session() as session:
        niche = NicheService(session).create_niche(
            name="  Practical niche  ",
            seed_keyword="  practical keyword  ",
            description="  A focused description.  ",
            notes="  Human note.  ",
        )

        assert niche.name == "Practical niche"
        assert niche.seed_keyword == "practical keyword"
        assert niche.description == "A focused description."
        assert niche.notes == "Human note."
        assert session.scalar(select(func.count(Niche.id))) == 1


@pytest.mark.parametrize(
    ("name", "seed_keyword"),
    [("", "keyword"), ("Name", "   ")],
)
def test_niche_creation_requires_name_and_seed_keyword(
    name: str,
    seed_keyword: str,
) -> None:
    with _session() as session:
        with pytest.raises(ValueError, match="Name and seed keyword are required"):
            NicheService(session).create_niche(name=name, seed_keyword=seed_keyword)

        assert session.scalar(select(func.count(Niche.id))) == 0


def test_duplicate_niche_name_is_rejected_without_losing_existing_record() -> None:
    with _session() as session:
        service = NicheService(session)
        existing = service.create_niche(name="Unique niche", seed_keyword="first")

        with pytest.raises(NicheNameConflict, match="already exists"):
            service.create_niche(name=" Unique niche ", seed_keyword="second")

        niches = list(session.scalars(select(Niche)))
        assert [niche.id for niche in niches] == [existing.id]
        assert niches[0].seed_keyword == "first"
