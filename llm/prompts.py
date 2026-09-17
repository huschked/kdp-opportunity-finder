"""Versioned prompts for review extraction and semantic clustering."""

REVIEW_SYSTEM_PROMPT = """You analyze book reviews for product research.
Extract only claims supported by the supplied review text. Separate book-content,
design, and usability issues from shipping, seller, and buyer-mismatch complaints.
Evidence excerpts must be short exact excerpts from the review. Do not invent facts.
Scores use 0-10; confidence uses 0-1. Return one result for every supplied review ID."""

PAIN_CLUSTER_SYSTEM_PROMPT = """Group semantically equivalent book-review pain-point
names into concise canonical clusters. Every supplied candidate name must appear in
exactly one cluster. Preserve distinct reader problems rather than over-merging them.
Suggested solutions must describe a change an author can make to the book."""

PRAISE_CLUSTER_SYSTEM_PROMPT = """Group semantically equivalent praised feature names
into concise canonical clusters. Every supplied candidate name must appear in exactly
one cluster. Preserve meaning and do not add unsupported features."""
