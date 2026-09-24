"""Corpus overview and ranked opportunity dashboard."""

import pandas as pd
import streamlit as st

from db.database import session_scope
from db.repositories import DashboardRepository
from ui.layout import render_empty_state


st.caption("Evidence-first niche research. Scores guide validation; they do not predict sales.")

with session_scope() as session:
    repository = DashboardRepository(session)
    totals = repository.totals()
    scores = repository.latest_scores()
    stages = repository.stage_counts()
    recent = repository.recent_analyses()

with st.container(horizontal=True):
    st.metric(
        "Niches",
        totals.niches,
        border=True,
        icon=":material/topic:",
        help="Research hypotheses stored in this local workspace.",
    )
    st.metric(
        "Competitor books",
        totals.books,
        border=True,
        icon=":material/library_books:",
        help="Observed competitor records across every niche.",
    )
    st.metric(
        "Review evidence",
        totals.reviews,
        border=True,
        icon=":material/reviews:",
        help="Stored source reviews; analysis does not replace the original text.",
    )
    st.metric(
        "Promising or later",
        totals.promising,
        border=True,
        icon=":material/trending_up:",
        help="Manual pipeline status only. Scores never move a niche automatically.",
    )

st.subheader("Ranked opportunities")
if scores:
    frame = pd.DataFrame(scores)
    st.dataframe(
        frame,
        hide_index=True,
        key="ranked_opportunities",
        column_config={
            "Opportunity": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f"),
            "Automated": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f"),
            "Confidence": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f"),
        },
    )
    low_confidence = frame.loc[frame["Confidence"] < 60, "Niche"].tolist()
    if low_confidence:
        st.warning(
            "Review the evidence before using these rankings: " + ", ".join(low_confidence),
            title="Low evidence confidence",
            icon=":material/warning:",
        )
else:
    render_empty_state(
        title="No decision scores yet",
        body="Ranked opportunities appear after a niche has an evidence-backed score snapshot.",
        next_step="Load the synthetic sample, or create a niche and calculate its first score from Niche detail.",
        icon="query_stats",
    )

left, right = st.columns(2)
with left:
    with st.container(border=True, height="stretch"):
        st.subheader("Niches by stage", icon=":material/view_kanban:")
        if stages:
            st.bar_chart(pd.DataFrame(stages).set_index("Stage"))
        else:
            st.caption("No pipeline stages are populated yet.")
with right:
    with st.container(border=True, height="stretch"):
        st.subheader("Recent analyses", icon=":material/history:")
        if recent:
            st.dataframe(
                pd.DataFrame(recent),
                hide_index=True,
                key="recent_analyses",
                column_config={
                    "Started": st.column_config.DatetimeColumn(format="MMM DD, YYYY · h:mm a"),
                },
            )
        else:
            st.caption("No review-analysis runs have been recorded yet.")
