from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from models import Base, Book, Niche, Review
from services.scoring_service import calculate_niche_score
from sample_data.generate import seed_sample_data


def test_sample_data_has_three_distinct_market_scenarios() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    assert seed_sample_data(session) is True
    assert session.scalar(select(func.count(Niche.id))) == 3
    assert session.scalar(select(func.count(Book.id))) == 30
    assert session.scalar(select(func.count(Review.id))) == 180
    assert seed_sample_data(session) is False


def test_phase4_scores_distinguish_the_three_sample_markets() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    assert seed_sample_data(session) is True
    niches = list(session.scalars(select(Niche).order_by(Niche.id)))
    scores = {niche.name: calculate_niche_score(session, niche.id) for niche in niches}

    attractive = scores["Apartment Balcony Gardening"]
    entrenched = scores["Home Coffee Roasting"]
    weak = scores["Antique Button Collecting"]
    assert attractive.automated_overall_score > entrenched.automated_overall_score
    assert attractive.automated_overall_score > weak.automated_overall_score
    assert entrenched.demand_score > weak.demand_score
    assert weak.competition_score > entrenched.competition_score
