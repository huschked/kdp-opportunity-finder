"""Niche workflows shared by Streamlit and tests."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db.repositories import NicheRepository
from models import Niche


class NicheNameConflict(ValueError):
    pass


class NicheService:
    def __init__(self, session: Session) -> None:
        self.repository = NicheRepository(session)
        self.session = session

    def create_niche(
        self,
        *,
        name: str,
        seed_keyword: str,
        description: str | None = None,
        notes: str | None = None,
    ) -> Niche:
        if not name.strip() or not seed_keyword.strip():
            raise ValueError("Name and seed keyword are required")
        try:
            niche = self.repository.create(
                name=name,
                seed_keyword=seed_keyword,
                description=description,
                notes=notes,
            )
            self.session.commit()
            return niche
        except IntegrityError as exc:
            self.session.rollback()
            raise NicheNameConflict(f'A niche named "{name.strip()}" already exists') from exc

