"""Corpus overview and ranked opportunity dashboard."""

import pandas as pd
import streamlit as st

from db.database import session_scope
from db.repositories import DashboardRepository


st.caption("Evidence-first niche research. Scores guide validation; they do not predict sales.")

with session_scope() as session:
    repository = DashboardRepository(session)
    totals = repository.totals()
    scores = repository.latest_scores()
    stages = repository.stage_counts()
    recent = repository.recent_analyses()

columns = st.columns(4)
columns[0].metric("Niches", totals.niches)
columns[1].metric("Books", totals.books)
columns[2].metric("Reviews", totals.reviews)
columns[3].metric("Promising+", totals.promising)

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
        st.warning("LOW DATA CONFIDENCE: " + ", ".join(low_confidence))
else:
    st.info("No scored niches yet. Load the synthetic sample or create a research niche.")

left, right = st.columns(2)
with left:
    st.subheader("Niches by stage")
    if stages:
        st.bar_chart(pd.DataFrame(stages).set_index("Stage"))
with right:
    st.subheader("Recent analyses")
    if recent:
        st.dataframe(pd.DataFrame(recent), hide_index=True, key="recent_analyses")
