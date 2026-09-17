"""Observable competitor summaries; no inferred sales figures."""

from __future__ import annotations

from typing import Any

import pandas as pd


def summarize_competitors(rows: list[dict[str, Any]]) -> dict[str, float | int | None]:
    if not rows:
        return {
            "book_count": 0,
            "median_price": None,
            "median_rating": None,
            "median_review_count": None,
            "median_page_count": None,
            "top_three_review_share": None,
        }
    frame = pd.DataFrame(rows)

    def median(column: str) -> float | None:
        values = pd.to_numeric(frame[column], errors="coerce").dropna()
        return round(float(values.median()), 2) if not values.empty else None

    reviews = pd.to_numeric(frame["review_count"], errors="coerce").dropna()
    review_share = None
    if not reviews.empty and float(reviews.sum()) > 0:
        review_share = round(float(reviews.nlargest(3).sum() / reviews.sum() * 100), 1)
    return {
        "book_count": len(frame),
        "median_price": median("price"),
        "median_rating": median("rating"),
        "median_review_count": median("review_count"),
        "median_page_count": median("page_count"),
        "top_three_review_share": review_share,
    }

