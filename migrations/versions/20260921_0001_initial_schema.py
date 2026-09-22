"""Establish the reviewed V1 schema baseline.

Revision ID: 20260921_0001
Revises: None
Create Date: 2026-09-21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260921_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "data_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=250), nullable=False),
        sa.Column("reference", sa.Text(), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_data_sources_source_type"),
        "data_sources",
        ["source_type"],
        unique=False,
    )
    op.create_table(
        "niches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=250), nullable=False),
        sa.Column("seed_keyword", sa.String(length=250), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_niches_name"), "niches", ["name"], unique=True)
    op.create_index(
        op.f("ix_niches_seed_keyword"), "niches", ["seed_keyword"], unique=False
    )
    op.create_index(op.f("ix_niches_status"), "niches", ["status"], unique=False)
    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("niche_id", sa.Integer(), nullable=False),
        sa.Column("analysis_type", sa.String(length=50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider", sa.String(length=80), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("prompt_version", sa.String(length=50), nullable=True),
        sa.Column("parameters_json", sa.JSON(), nullable=True),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["niche_id"], ["niches.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_analysis_runs_analysis_type"),
        "analysis_runs",
        ["analysis_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analysis_runs_niche_id"),
        "analysis_runs",
        ["niche_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analysis_runs_status"),
        "analysis_runs",
        ["status"],
        unique=False,
    )
    op.create_table(
        "books",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("niche_id", sa.Integer(), nullable=False),
        sa.Column("data_source_id", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("source_identifier", sa.String(length=160), nullable=True),
        sa.Column("asin", sa.String(length=20), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("subtitle", sa.String(length=500), nullable=True),
        sa.Column("author", sa.String(length=250), nullable=True),
        sa.Column("publisher", sa.String(length=250), nullable=True),
        sa.Column("publication_date", sa.Date(), nullable=True),
        sa.Column("format", sa.String(length=50), nullable=True),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("review_count", sa.Integer(), nullable=True),
        sa.Column("best_seller_rank", sa.Integer(), nullable=True),
        sa.Column("category", sa.String(length=250), nullable=True),
        sa.Column("product_reference", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("cover_image_reference", sa.Text(), nullable=True),
        sa.Column("date_collected", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "rating IS NULL OR (rating >= 0 AND rating <= 5)",
            name="ck_book_rating",
        ),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"]),
        sa.ForeignKeyConstraint(["niche_id"], ["niches.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source", "source_identifier", name="uq_book_source_identifier"
        ),
    )
    op.create_index(op.f("ix_books_asin"), "books", ["asin"], unique=False)
    op.create_index(
        op.f("ix_books_niche_id"), "books", ["niche_id"], unique=False
    )
    op.create_index(
        op.f("ix_books_source_identifier"),
        "books",
        ["source_identifier"],
        unique=False,
    )
    op.create_table(
        "import_batches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=30), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_count", sa.Integer(), nullable=False),
        sa.Column("imported_count", sa.Integer(), nullable=False),
        sa.Column("rejected_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("errors_json", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["source_id"], ["data_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_import_batches_source_id"),
        "import_batches",
        ["source_id"],
        unique=False,
    )
    op.create_table(
        "niche_status_transitions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("niche_id", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.String(length=30), nullable=False),
        sa.Column("to_status", sa.String(length=30), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["niche_id"], ["niches.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_niche_status_transitions_changed_at"),
        "niche_status_transitions",
        ["changed_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_niche_status_transitions_niche_id"),
        "niche_status_transitions",
        ["niche_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_niche_status_transitions_to_status"),
        "niche_status_transitions",
        ["to_status"],
        unique=False,
    )
    op.create_table(
        "pain_points",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("niche_id", sa.Integer(), nullable=False),
        sa.Column("canonical_name", sa.String(length=250), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("system_solvability_score", sa.Float(), nullable=True),
        sa.Column("human_solvability_score", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("suggested_solution", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["niche_id"], ["niches.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "niche_id", "canonical_name", name="uq_pain_niche_name"
        ),
    )
    op.create_index(
        op.f("ix_pain_points_niche_id"),
        "pain_points",
        ["niche_id"],
        unique=False,
    )
    op.create_table(
        "praise_features",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("niche_id", sa.Integer(), nullable=False),
        sa.Column("canonical_name", sa.String(length=250), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["niche_id"], ["niches.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "niche_id", "canonical_name", name="uq_praise_niche_name"
        ),
    )
    op.create_index(
        op.f("ix_praise_features_niche_id"),
        "praise_features",
        ["niche_id"],
        unique=False,
    )
    op.create_table(
        "score_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("niche_id", sa.Integer(), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scoring_version", sa.String(length=30), nullable=False),
        sa.Column("demand_score", sa.Float(), nullable=False),
        sa.Column("competition_score", sa.Float(), nullable=False),
        sa.Column("customer_gap_score", sa.Float(), nullable=False),
        sa.Column("economics_score", sa.Float(), nullable=False),
        sa.Column("ai_suitability_score", sa.Float(), nullable=False),
        sa.Column("expansion_score", sa.Float(), nullable=False),
        sa.Column("automated_overall_score", sa.Float(), nullable=False),
        sa.Column("human_overall_score", sa.Float(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("unmet_demand_index", sa.Float(), nullable=True),
        sa.Column("weights_json", sa.JSON(), nullable=False),
        sa.Column("explanation_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["niche_id"], ["niches.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_score_snapshots_calculated_at"),
        "score_snapshots",
        ["calculated_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_score_snapshots_niche_id"),
        "score_snapshots",
        ["niche_id"],
        unique=False,
    )
    op.create_table(
        "book_concepts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("niche_id", sa.Integer(), nullable=False),
        sa.Column("analysis_run_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("concept_json", sa.JSON(), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"]),
        sa.ForeignKeyConstraint(["niche_id"], ["niches.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_book_concepts_niche_id"),
        "book_concepts",
        ["niche_id"],
        unique=False,
    )
    op.create_table(
        "market_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("book_id", sa.Integer(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("review_count", sa.Integer(), nullable=True),
        sa.Column("best_seller_rank", sa.Integer(), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_market_snapshots_book_id"),
        "market_snapshots",
        ["book_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_market_snapshots_observed_at"),
        "market_snapshots",
        ["observed_at"],
        unique=False,
    )
    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("book_id", sa.Integer(), nullable=False),
        sa.Column("data_source_id", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("source_review_identifier", sa.String(length=160), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("raw_body", sa.Text(), nullable=False),
        sa.Column("normalized_body", sa.Text(), nullable=False),
        sa.Column("normalized_hash", sa.String(length=64), nullable=False),
        sa.Column("review_date", sa.Date(), nullable=True),
        sa.Column("verified_purchase", sa.Boolean(), nullable=True),
        sa.Column("helpful_votes", sa.Integer(), nullable=True),
        sa.Column("date_collected", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "rating IS NULL OR (rating >= 1 AND rating <= 5)",
            name="ck_review_rating",
        ),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"]),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "book_id", "normalized_hash", name="uq_review_book_hash"
        ),
    )
    op.create_index(
        op.f("ix_reviews_book_id"), "reviews", ["book_id"], unique=False
    )
    op.create_index(
        op.f("ix_reviews_normalized_hash"),
        "reviews",
        ["normalized_hash"],
        unique=False,
    )
    op.create_index(op.f("ix_reviews_rating"), "reviews", ["rating"], unique=False)
    op.create_index(
        op.f("ix_reviews_source_review_identifier"),
        "reviews",
        ["source_review_identifier"],
        unique=False,
    )
    op.create_table(
        "review_analyses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("analysis_run_id", sa.Integer(), nullable=True),
        sa.Column("sentiment", sa.String(length=30), nullable=True),
        sa.Column("topics_json", sa.JSON(), nullable=True),
        sa.Column("features_json", sa.JSON(), nullable=True),
        sa.Column("desired_outcomes_json", sa.JSON(), nullable=True),
        sa.Column("reader_skill_level", sa.String(length=50), nullable=True),
        sa.Column("purchase_motivation", sa.Text(), nullable=True),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("schema_version", sa.String(length=30), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"]),
        sa.ForeignKeyConstraint(["review_id"], ["reviews.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_review_analyses_content_hash"),
        "review_analyses",
        ["content_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_review_analyses_review_id"),
        "review_analyses",
        ["review_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_review_analyses_sentiment"),
        "review_analyses",
        ["sentiment"],
        unique=False,
    )
    op.create_table(
        "review_pain_points",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("pain_point_id", sa.Integer(), nullable=False),
        sa.Column("severity", sa.Float(), nullable=False),
        sa.Column("solvable", sa.Boolean(), nullable=False),
        sa.Column("extraction_text", sa.Text(), nullable=True),
        sa.Column("extraction_json", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["pain_point_id"], ["pain_points.id"]),
        sa.ForeignKeyConstraint(["review_id"], ["reviews.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "review_id", "pain_point_id", name="uq_review_pain"
        ),
    )
    op.create_index(
        op.f("ix_review_pain_points_pain_point_id"),
        "review_pain_points",
        ["pain_point_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_review_pain_points_review_id"),
        "review_pain_points",
        ["review_id"],
        unique=False,
    )
    op.create_table(
        "review_praise_features",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("praise_feature_id", sa.Integer(), nullable=False),
        sa.Column("strength", sa.Float(), nullable=False),
        sa.Column("extraction_text", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["praise_feature_id"], ["praise_features.id"]),
        sa.ForeignKeyConstraint(["review_id"], ["reviews.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "review_id", "praise_feature_id", name="uq_review_praise"
        ),
    )
    op.create_index(
        op.f("ix_review_praise_features_praise_feature_id"),
        "review_praise_features",
        ["praise_feature_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_review_praise_features_review_id"),
        "review_praise_features",
        ["review_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_review_praise_features_review_id"),
        table_name="review_praise_features",
    )
    op.drop_index(
        op.f("ix_review_praise_features_praise_feature_id"),
        table_name="review_praise_features",
    )
    op.drop_table("review_praise_features")
    op.drop_index(
        op.f("ix_review_pain_points_review_id"), table_name="review_pain_points"
    )
    op.drop_index(
        op.f("ix_review_pain_points_pain_point_id"),
        table_name="review_pain_points",
    )
    op.drop_table("review_pain_points")
    op.drop_index(
        op.f("ix_review_analyses_sentiment"), table_name="review_analyses"
    )
    op.drop_index(
        op.f("ix_review_analyses_review_id"), table_name="review_analyses"
    )
    op.drop_index(
        op.f("ix_review_analyses_content_hash"), table_name="review_analyses"
    )
    op.drop_table("review_analyses")
    op.drop_index(
        op.f("ix_reviews_source_review_identifier"), table_name="reviews"
    )
    op.drop_index(op.f("ix_reviews_rating"), table_name="reviews")
    op.drop_index(op.f("ix_reviews_normalized_hash"), table_name="reviews")
    op.drop_index(op.f("ix_reviews_book_id"), table_name="reviews")
    op.drop_table("reviews")
    op.drop_index(
        op.f("ix_market_snapshots_observed_at"), table_name="market_snapshots"
    )
    op.drop_index(
        op.f("ix_market_snapshots_book_id"), table_name="market_snapshots"
    )
    op.drop_table("market_snapshots")
    op.drop_index(op.f("ix_book_concepts_niche_id"), table_name="book_concepts")
    op.drop_table("book_concepts")
    op.drop_index(
        op.f("ix_score_snapshots_niche_id"), table_name="score_snapshots"
    )
    op.drop_index(
        op.f("ix_score_snapshots_calculated_at"), table_name="score_snapshots"
    )
    op.drop_table("score_snapshots")
    op.drop_index(
        op.f("ix_praise_features_niche_id"), table_name="praise_features"
    )
    op.drop_table("praise_features")
    op.drop_index(op.f("ix_pain_points_niche_id"), table_name="pain_points")
    op.drop_table("pain_points")
    op.drop_index(
        op.f("ix_niche_status_transitions_to_status"),
        table_name="niche_status_transitions",
    )
    op.drop_index(
        op.f("ix_niche_status_transitions_niche_id"),
        table_name="niche_status_transitions",
    )
    op.drop_index(
        op.f("ix_niche_status_transitions_changed_at"),
        table_name="niche_status_transitions",
    )
    op.drop_table("niche_status_transitions")
    op.drop_index(
        op.f("ix_import_batches_source_id"), table_name="import_batches"
    )
    op.drop_table("import_batches")
    op.drop_index(op.f("ix_books_source_identifier"), table_name="books")
    op.drop_index(op.f("ix_books_niche_id"), table_name="books")
    op.drop_index(op.f("ix_books_asin"), table_name="books")
    op.drop_table("books")
    op.drop_index(op.f("ix_analysis_runs_status"), table_name="analysis_runs")
    op.drop_index(op.f("ix_analysis_runs_niche_id"), table_name="analysis_runs")
    op.drop_index(
        op.f("ix_analysis_runs_analysis_type"), table_name="analysis_runs"
    )
    op.drop_table("analysis_runs")
    op.drop_index(op.f("ix_niches_status"), table_name="niches")
    op.drop_index(op.f("ix_niches_seed_keyword"), table_name="niches")
    op.drop_index(op.f("ix_niches_name"), table_name="niches")
    op.drop_table("niches")
    op.drop_index(
        op.f("ix_data_sources_source_type"), table_name="data_sources"
    )
    op.drop_table("data_sources")
