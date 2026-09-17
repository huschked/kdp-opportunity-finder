from analysis.market import summarize_competitors


def test_competitor_summary_ignores_missing_values() -> None:
    summary = summarize_competitors([
        {"price": 10, "rating": 4.0, "review_count": 100, "page_count": 100},
        {"price": 20, "rating": 4.5, "review_count": 50, "page_count": None},
        {"price": None, "rating": None, "review_count": 25, "page_count": 200},
        {"price": 30, "rating": 5.0, "review_count": 25, "page_count": 300},
    ])
    assert summary["book_count"] == 4
    assert summary["median_price"] == 20
    assert summary["median_review_count"] == 37.5
    assert summary["top_three_review_share"] == 87.5

