"""Create three deterministic, copyright-safe market scenarios."""

from __future__ import annotations

from datetime import date, timedelta
import hashlib
import random

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import (
    AnalysisRun,
    Book,
    DataSource,
    MarketSnapshot,
    Niche,
    PainPoint,
    PraiseFeature,
    Review,
    ReviewPainPoint,
    ReviewPraiseFeature,
)
from services.scoring_service import calculate_niche_score


SCENARIOS = (
    {
        "name": "Home Coffee Roasting",
        "seed": "home coffee roasting",
        "description": "High observed demand with polished, entrenched competition.",
        "status": "researching",
        "base_reviews": 1850,
        "rating": 4.7,
        "price": 19.99,
        "complaint": "The explanations are useful, but this edition needed a few more worked roast profiles for beginners.",
        "praise": "The temperature charts and clear step-by-step process made my first roast much easier.",
        "pain": "Not enough worked roast profiles",
        "feature": "Clear temperature charts",
        "solvability": 8.8,
    },
    {
        "name": "Apartment Balcony Gardening",
        "seed": "balcony gardening for renters",
        "description": "Moderate-to-high traction, repeated cross-book gaps, and accessible competition.",
        "status": "promising",
        "base_reviews": 340,
        "rating": 4.25,
        "price": 16.49,
        "complaint": "I wanted practical layouts for tiny shaded balconies, not general garden theory and large-yard examples.",
        "praise": "The seasonal checklist and container diagrams are exactly what a renter needs.",
        "pain": "Too few small-space worked layouts",
        "feature": "Seasonal renter checklists",
        "solvability": 9.4,
    },
    {
        "name": "Antique Button Collecting",
        "seed": "antique button collecting guide",
        "description": "Low competitive pressure but weak observed demand.",
        "status": "discovered",
        "base_reviews": 38,
        "rating": 4.35,
        "price": 13.99,
        "complaint": "The identification section could use more close-up comparison examples and clearer era labels.",
        "praise": "The historical notes are concise and pleasant to browse.",
        "pain": "Limited identification comparisons",
        "feature": "Concise historical context",
        "solvability": 7.2,
    },
)


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def seed_sample_data(session: Session, *, force: bool = False) -> bool:
    existing = session.scalar(select(func.count(Niche.id))) or 0
    if existing and not force:
        return False

    rng = random.Random(20260907)
    source = DataSource(
        source_type="synthetic",
        name="Built-in Phase 1 demonstration data",
        notes="Generated text; not copied from marketplace reviews.",
    )
    session.add(source)
    session.flush()
    for scenario_index, scenario in enumerate(SCENARIOS, start=1):
        niche = Niche(
            name=scenario["name"],
            seed_keyword=scenario["seed"],
            description=scenario["description"],
            status=scenario["status"],
            notes="Synthetic scenario for validating score behavior.",
        )
        session.add(niche)
        session.flush()

        pain = PainPoint(
            niche_id=niche.id,
            canonical_name=scenario["pain"],
            description=scenario["complaint"],
            system_solvability_score=scenario["solvability"],
            confidence=78,
            suggested_solution="Add specific, worked, visual examples addressing the repeated request.",
        )
        praise = PraiseFeature(
            niche_id=niche.id,
            canonical_name=scenario["feature"],
            description=scenario["praise"],
            confidence=76,
        )
        session.add_all((pain, praise))
        session.flush()

        for book_index in range(1, 11):
            review_count = max(4, int(scenario["base_reviews"] * (1.2 - book_index * 0.075)))
            book = Book(
                niche_id=niche.id,
                data_source_id=source.id,
                source="synthetic",
                source_identifier=f"SYN-{scenario_index}-{book_index:02d}",
                title=f"{scenario['name']}: Practical Guide {book_index}",
                author=f"Sample Author {book_index}",
                publisher="Independent" if book_index > 3 else f"Sample Press {book_index}",
                publication_date=date.today() - timedelta(days=210 * book_index),
                format="Paperback" if book_index % 3 else "eBook",
                price=round(float(scenario["price"]) + rng.uniform(-3, 3), 2),
                page_count=120 + book_index * 9,
                rating=round(float(scenario["rating"]) + rng.uniform(-0.22, 0.15), 1),
                review_count=review_count,
                best_seller_rank=max(900, int(180000 / max(review_count, 1))) * (book_index + 1),
                category=scenario["name"],
                date_collected=date.today(),
            )
            session.add(book)
            session.flush()
            session.add(MarketSnapshot(
                book_id=book.id,
                price=book.price,
                rating=book.rating,
                review_count=book.review_count,
                best_seller_rank=book.best_seller_rank,
            ))

            for review_index in range(1, 7):
                negative = review_index in (1, 4)
                body = (
                    f"{scenario['complaint']} Example review {book_index}-{review_index}."
                    if negative
                    else f"{scenario['praise']} Example review {book_index}-{review_index}."
                )
                normalized = _normalize(body)
                review = Review(
                    book_id=book.id,
                    data_source_id=source.id,
                    source="synthetic",
                    source_review_identifier=f"SYN-R-{scenario_index}-{book_index}-{review_index}",
                    rating=2 if negative else rng.choice((4, 5)),
                    title="Needs more practical depth" if negative else "Useful and clear",
                    raw_body=body,
                    normalized_body=normalized,
                    normalized_hash=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
                    review_date=date.today() - timedelta(days=review_index * 13 + book_index),
                    verified_purchase=None,
                    helpful_votes=review_index % 3,
                )
                session.add(review)
                session.flush()
                if negative:
                    session.add(ReviewPainPoint(
                        review_id=review.id,
                        pain_point_id=pain.id,
                        severity=7.0 + scenario_index * 0.5,
                        solvable=True,
                        extraction_text=scenario["complaint"],
                    ))
                else:
                    session.add(ReviewPraiseFeature(
                        review_id=review.id,
                        praise_feature_id=praise.id,
                        strength=7.5,
                        extraction_text=scenario["praise"],
                    ))

        session.add(AnalysisRun(
            niche_id=niche.id,
            analysis_type="synthetic_baseline",
            provider="mock",
            model="deterministic-sample-v1",
            prompt_version="sample-1",
            status="completed",
            result_json={"note": "Synthetic baseline only; not marketplace evidence."},
        ))
        session.flush()
        calculate_niche_score(session, niche.id)

    session.commit()
    return True
