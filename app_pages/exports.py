"""Dedicated downloads for traceable research and decision data."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from db.database import session_scope
from services.export_service import (
    BOOKS_EXPORT,
    DECISIONS_EXPORT,
    EXPORT_DESCRIPTIONS,
    EXPORT_LABELS,
    EXPORT_TYPES,
    MISSING_VALUE_POLICY,
    REVIEWS_EXPORT,
    ExportDataset,
    build_export_dataset,
    list_export_niches,
    render_export_csv,
    render_export_json,
)
from ui.errors import render_operation_error
from ui.layout import render_empty_state


def _preview_frame(dataset: ExportDataset) -> pd.DataFrame:
    if dataset.export_type == DECISIONS_EXPORT:
        fields = {
            "niche_id": "Niche ID",
            "niche_name": "Niche",
            "status": "Status",
            "score_snapshot_id": "Score snapshot",
            "automated_score": "Automated score",
            "human_adjusted_score": "Human-adjusted score",
            "decision_score": "Decision score",
            "confidence_score": "Confidence",
            "unmet_demand_index": "UDI",
            "recommendation": "Recommendation",
            "confidence_warnings": "Warnings",
            "missing_observations": "Missing observations",
        }
    elif dataset.export_type == BOOKS_EXPORT:
        fields = {
            "book_id": "Book ID",
            "niche_id": "Niche ID",
            "data_source_id": "Data source ID",
            "source_identifier": "Source identifier",
            "title": "Title",
            "price": "Price",
            "rating": "Rating",
            "review_count": "Review count",
            "best_seller_rank": "BSR",
            "latest_market_snapshot_id": "Market snapshot",
        }
    else:
        fields = {
            "review_id": "Review ID",
            "book_id": "Book ID",
            "niche_id": "Niche ID",
            "data_source_id": "Data source ID",
            "source_review_identifier": "Source review ID",
            "rating": "Rating",
            "title": "Title",
            "review_date": "Review date",
            "review_analysis_id": "Analysis ID",
            "pain_point_links": "Pain links",
            "praise_feature_links": "Praise links",
        }
    return pd.DataFrame(
        [
            {label: record.get(field) for field, label in fields.items()}
            for record in dataset.records[:100]
        ],
        columns=list(fields.values()),
    )


st.caption(
    "Download stored research and the latest decision snapshots without losing database IDs, source provenance, "
    "or uncertainty. Exports never estimate missing marketplace values."
)

try:
    with session_scope() as session:
        niches = list_export_niches(session)
except Exception as exc:
    render_operation_error(
        exc,
        operation="export.load_scope",
        summary="Export options could not be loaded.",
        recovery="Refresh the page and try again. Existing research was not changed.",
    )
    st.stop()

if not niches:
    render_empty_state(
        title="No research available to export",
        body="Exports preserve stored IDs, provenance, missing values, and evidence warnings without inventing records.",
        next_step="Create a niche in Research or load the synthetic sample from the sidebar.",
        icon="download",
    )
    st.stop()

export_type = st.segmented_control(
    "Dataset",
    options=list(EXPORT_TYPES),
    default=DECISIONS_EXPORT,
    required=True,
    format_func=lambda value: EXPORT_LABELS[value],
    width="stretch",
    key="export_dataset",
)
assert export_type is not None
st.caption(EXPORT_DESCRIPTIONS[export_type])

niche_by_id = {niche.niche_id: niche for niche in niches}
preferred_niche_id = st.session_state.get("selected_niche_id")
default_niche_index = (
    list(niche_by_id).index(preferred_niche_id)
    if preferred_niche_id in niche_by_id
    else 0
)

if export_type == DECISIONS_EXPORT:
    scope_options: list[int | None] = [None, *niche_by_id]
    selected_niche_id = st.selectbox(
        "Scope",
        options=scope_options,
        format_func=lambda value: (
            "All niches"
            if value is None
            else f"{niche_by_id[value].niche_name} · N{value}"
        ),
        key="export_decision_scope",
        help="All niches exports each niche's latest saved score snapshot; choose one niche for a focused file.",
    )
else:
    selected_niche_id = st.selectbox(
        "Niche",
        options=list(niche_by_id),
        index=default_niche_index,
        format_func=lambda value: f"{niche_by_id[value].niche_name} · N{value}",
        key=f"export_{export_type}_niche",
    )

try:
    with session_scope() as session:
        dataset = build_export_dataset(
            session,
            export_type=export_type,
            niche_id=selected_niche_id,
        )
except Exception as exc:
    render_operation_error(
        exc,
        operation="export.build",
        summary="The export dataset could not be created.",
        recovery="Review the selected scope and try again. No download was produced.",
        context={
            "export_type": export_type,
            "niche_id": selected_niche_id,
        },
        expected=isinstance(exc, ValueError),
    )
    st.stop()

scope_name = (
    "All niches"
    if dataset.scope.get("kind") == "all_niches"
    else f"{dataset.scope['niche_name']} · N{dataset.scope['niche_id']}"
)
with st.container(horizontal=True):
    st.metric("Records", dataset.record_count, border=True, icon=":material/table_rows:")
    st.metric("Scope", scope_name, border=True, icon=":material/filter_alt:")
    st.metric("Columns", len(dataset.columns), border=True, icon=":material/view_column:")

for warning in dataset.dataset_warnings:
    st.warning(warning)

st.subheader("Preview", icon=":material/preview:")
st.caption(
    "The preview shows selected high-value columns and at most 100 records. Downloads contain the full declared schema."
)
if dataset.records:
    st.dataframe(
        _preview_frame(dataset),
        hide_index=True,
        key=f"export_preview_{export_type}",
    )
else:
    render_empty_state(
        title="The selected export is empty",
        body="The scope is valid, but no stored records meet its declared dataset rules.",
        next_step="Choose another scope or add the required evidence before downloading.",
        icon="inventory_2",
    )

try:
    csv_data = render_export_csv(dataset)
    json_data = render_export_json(dataset)
except Exception as exc:
    render_operation_error(
        exc,
        operation="export.render",
        summary="The export files could not be rendered.",
        recovery="No download was produced. Try again and use the error reference if the failure repeats.",
        context={
            "export_type": export_type,
            "niche_id": selected_niche_id,
            "record_count": dataset.record_count,
        },
    )
    st.stop()
csv_filename = dataset.filename("csv")
json_filename = dataset.filename("json")

st.subheader("Download", icon=":material/download:")
with st.container(horizontal=True):
    st.download_button(
        "Download CSV",
        data=csv_data,
        file_name=csv_filename,
        mime="text/csv; charset=utf-8",
        icon=":material/download:",
        on_click="ignore",
        width="stretch",
        key=f"download_{export_type}_csv_{selected_niche_id}",
    )
    st.download_button(
        "Download JSON",
        data=json_data,
        file_name=json_filename,
        mime="application/json",
        icon=":material/download:",
        on_click="ignore",
        width="stretch",
        key=f"download_{export_type}_json_{selected_niche_id}",
    )
st.caption(f"Files: `{csv_filename}` and `{json_filename}`")

with st.expander("Schema and safeguards", icon=":material/shield:"):
    st.write(MISSING_VALUE_POLICY)
    st.write(
        "CSV stores nested warnings, explanations, and evidence links as JSON text. JSON preserves them as native "
        "arrays and objects and adds an export manifest with the scope, generated time, record count, and warnings."
    )
    st.write("Columns in download order:")
    st.code("\n".join(dataset.columns), language=None)
