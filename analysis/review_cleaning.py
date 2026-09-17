"""Lossless review cleaning helpers."""

from __future__ import annotations

import hashlib
import re
import unicodedata


_WHITESPACE = re.compile(r"\s+")


def normalize_review_text(text: str) -> str:
    """Normalize Unicode and whitespace while retaining readable content."""

    normalized = unicodedata.normalize("NFKC", text)
    return _WHITESPACE.sub(" ", normalized).strip()


def review_text_hash(text: str) -> str:
    canonical = normalize_review_text(text).casefold()
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

