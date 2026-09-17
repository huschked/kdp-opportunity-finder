"""Human corrections for canonical pain-point groups."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import PainPoint, ReviewPainPoint


def rename_pain_point(session: Session, *, pain_point_id: int, canonical_name: str) -> PainPoint:
    point = session.get(PainPoint, pain_point_id)
    if point is None:
        raise ValueError("Pain point not found.")
    name = canonical_name.strip()
    if not name:
        raise ValueError("Canonical name is required.")
    duplicate = session.scalar(select(PainPoint).where(
        PainPoint.niche_id == point.niche_id,
        PainPoint.canonical_name == name,
        PainPoint.id != point.id,
    ))
    if duplicate:
        raise ValueError("That canonical name already exists; merge the groups instead.")
    point.canonical_name = name
    session.flush()
    return point


def merge_pain_points(session: Session, *, source_id: int, target_id: int) -> PainPoint:
    if source_id == target_id:
        raise ValueError("Choose two different pain points.")
    source = session.get(PainPoint, source_id)
    target = session.get(PainPoint, target_id)
    if source is None or target is None or source.niche_id != target.niche_id:
        raise ValueError("Both pain points must exist in the same niche.")
    target_links = {link.review_id: link for link in target.review_links}
    for link in list(source.review_links):
        existing = target_links.get(link.review_id)
        if existing:
            existing.severity = max(existing.severity, link.severity)
            existing.solvable = existing.solvable or link.solvable
            session.delete(link)
        else:
            link.pain_point = target
    source.human_solvability_score = None
    session.delete(source)
    session.flush()
    return target
