from analysis.review_cleaning import normalize_review_text, review_text_hash


def test_normalization_is_lossless_except_unicode_and_whitespace() -> None:
    assert normalize_review_text("  More\n\tworked   examples — please. ") == "More worked examples — please."
    assert review_text_hash("Needs  Examples") == review_text_hash(" needs examples ")

