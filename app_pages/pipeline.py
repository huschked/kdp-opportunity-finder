"""Human-controlled workflow pipeline for researched niches."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from db.database import session_scope
from services.pipeline_service import (
    STATUS_LABELS,
    STATUS_ORDER,
    PipelineRow,
    change_niche_status,
    filter_pipeline,
    load_pipeline,
    status_history,
)
from ui.errors import render_operation_error


def _pipeline_frame(rows: tuple[PipelineRow, ...]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Niche": row.niche_name,
                "Status": row.status_label,
                "Seed keyword": row.seed_keyword,
                "Automated score": row.automated_score,
                "Human-adjusted score": row.human_adjusted_score,
                "Decision score": row.decision_score,
                "Confidence": row.confidence,
                "UDI": row.unmet_demand_index,
                "Recommendation": row.recommendation,
                "Evidence warnings": row.warning_count,
                "Score snapshot": row.snapshot_id,
                "Updated": row.niche_updated_at,
            }
            for row in rows
        ]
    )


st.caption(
    "Track research from discovery through publication while keeping every status change explicit and auditable. "
    "Pipeline status never changes automatically from a score or recommendation."
)

status_message = st.session_state.pop("pipeline_status_message", None)
if status_message:
    st.success(status_message)

with session_scope() as session:
    full_pipeline = load_pipeline(session)
    history_rows = status_history(session, limit=50)

if not full_pipeline.total_count:
    st.info("Add a niche or load the synthetic sample before using the pipeline.")
    st.stop()

with st.container(horizontal=True):
    st.metric("Total niches", full_pipeline.total_count, border=True)
    st.metric("Active workflow", full_pipeline.active_count, border=True)
    st.metric("Published", full_pipeline.stage_counts.get("published", 0), border=True)
    st.metric(
        "Rejected or archived",
        full_pipeline.stage_counts.get("rejected", 0)
        + full_pipeline.stage_counts.get("archived", 0),
        border=True,
    )

st.subheader("Pipeline stages")
stage_frame = pd.DataFrame(
    [
        {"Stage": STATUS_LABELS[status], "Niches": full_pipeline.stage_counts.get(status, 0)}
        for status in STATUS_ORDER
    ]
)
stage_frame["Stage"] = pd.Categorical(
    stage_frame["Stage"],
    categories=[STATUS_LABELS[status] for status in STATUS_ORDER],
    ordered=True,
)
st.bar_chart(stage_frame, x="Stage", y="Niches", sort=False, height=300)

st.subheader("Niches")
with st.form("pipeline_filters", border=False):
    filter_columns = st.columns([1, 2])
    with filter_columns[0]:
        search_query = st.text_input(
            "Search niches",
            key="pipeline_search",
            placeholder="Name or seed keyword",
        )
    with filter_columns[1]:
        selected_statuses = st.multiselect(
            "Filter by status",
            options=list(STATUS_ORDER),
            format_func=lambda status: STATUS_LABELS[status],
            key="pipeline_status_filter",
            placeholder="All statuses",
        )
    st.form_submit_button("Apply filters", icon=":material/filter_alt:")

filtered_pipeline = filter_pipeline(
    full_pipeline,
    statuses=selected_statuses,
    query=search_query,
)

st.caption(
    f"Showing {filtered_pipeline.visible_count} of {filtered_pipeline.total_count} niches. "
    "Decision context comes from each niche's latest immutable score snapshot."
)
if filtered_pipeline.rows:
    st.dataframe(
        _pipeline_frame(filtered_pipeline.rows),
        hide_index=True,
        key="pipeline_table",
        column_config={
            "Niche": st.column_config.TextColumn(pinned=True),
            "Automated score": st.column_config.NumberColumn(format="%.1f"),
            "Human-adjusted score": st.column_config.NumberColumn(format="%.1f"),
            "Decision score": st.column_config.ProgressColumn(
                min_value=0, max_value=100, format="%.1f", color="blue"
            ),
            "Confidence": st.column_config.ProgressColumn(
                min_value=0, max_value=100, format="%.1f", color="auto"
            ),
            "UDI": st.column_config.NumberColumn(format="%.1f"),
            "Evidence warnings": st.column_config.NumberColumn(format="%d"),
            "Score snapshot": st.column_config.NumberColumn(format="%d"),
            "Updated": st.column_config.DatetimeColumn(format="MMM DD, YYYY · h:mm a"),
        },
    )
else:
    st.info("No niches match the current pipeline filters.")

st.subheader("Record a status change")
st.caption(
    "This updates only the local workflow label. It does not publish, reject, score, or otherwise change a book decision."
)
row_by_id = {row.niche_id: row for row in full_pipeline.rows}
selected_niche_id = st.selectbox(
    "Niche to move",
    options=list(row_by_id),
    format_func=lambda niche_id: row_by_id[niche_id].niche_name,
    key="pipeline_move_niche",
)
selected_row = row_by_id[selected_niche_id]
st.info(f"Current status: **{selected_row.status_label}**")

with st.form("pipeline_status_change", clear_on_submit=True):
    new_status = st.selectbox(
        "New status",
        options=list(STATUS_ORDER),
        index=list(STATUS_ORDER).index(selected_row.status),
        format_func=lambda status: STATUS_LABELS[status],
        key=f"pipeline_new_status_{selected_niche_id}",
    )
    rationale = st.text_area(
        "Rationale",
        placeholder="Record why this niche is moving to the new stage.",
        key=f"pipeline_status_rationale_{selected_niche_id}",
    )
    submitted = st.form_submit_button(
        "Save status change",
        type="primary",
        icon=":material/save:",
    )

if submitted:
    try:
        with session_scope() as session:
            transition = change_niche_status(
                session,
                niche_id=selected_niche_id,
                new_status=new_status,
                rationale=rationale,
            )
    except ValueError as exc:
        render_operation_error(
            exc,
            operation="pipeline.status_change",
            summary="The pipeline status was not changed.",
            recovery="Choose a different valid status and provide a rationale, then try again.",
            context={"niche_id": selected_niche_id},
            expected=True,
        )
    else:
        st.session_state["pipeline_status_message"] = (
            f"Moved {selected_row.niche_name} from "
            f"{STATUS_LABELS.get(transition.from_status, transition.from_status.title())} to "
            f"{STATUS_LABELS[transition.to_status]}."
        )
        st.rerun()

st.subheader("Status history")
if history_rows:
    history_frame = pd.DataFrame(
        [
            {
                "Changed": row.changed_at,
                "Niche": row.niche_name,
                "From": STATUS_LABELS.get(row.from_status, row.from_status.title()),
                "To": STATUS_LABELS.get(row.to_status, row.to_status.title()),
                "Rationale": row.rationale,
            }
            for row in history_rows
        ]
    )
    st.dataframe(
        history_frame,
        hide_index=True,
        key="pipeline_history_table",
        column_config={
            "Changed": st.column_config.DatetimeColumn(format="MMM DD, YYYY · h:mm a"),
            "Niche": st.column_config.TextColumn(pinned=True),
            "Rationale": st.column_config.TextColumn(width="large"),
        },
    )
else:
    st.info("No status changes have been recorded yet.")
