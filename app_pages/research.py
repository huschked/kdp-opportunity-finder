"""Niche creation and Phase 2 ingestion workflows."""

import pandas as pd
import streamlit as st

from ui.research_panels import (
    load_niches,
    render_create_niche,
    render_import,
    render_manual_book,
)
from ui.analysis_panel import render_analysis_panel


st.caption("Create hypotheses, then add observed competitor and review evidence.")

flash = st.session_state.pop("phase2_import_flash", None)
if flash:
    st.success(
        f"Import batch {flash['batch_id']} finished: {flash['processed_count']} processed, "
        f"{flash['imported_count']} imported, {flash['rejected_count']} rejected."
    )

analysis_flash = st.session_state.pop("phase3_analysis_flash", None)
if analysis_flash:
    st.success(
        f"Analysis run {analysis_flash.run_id} completed: {analysis_flash.analyzed_count} analyzed, "
        f"{analysis_flash.cached_count} reused, {analysis_flash.pain_point_count} pain-point groups, "
        f"and {analysis_flash.praise_feature_count} praised-feature groups."
    )

mode = st.selectbox(
    "Research task",
    ("Create niche", "Add or edit book", "Import books", "Import reviews", "Analyze reviews"),
    index=0,
    key="research_task",
)
niches = load_niches()

if mode == "Create niche":
    render_create_niche()
elif mode == "Add or edit book":
    render_manual_book(niches)
elif mode == "Import books":
    render_import(niches, "book")
elif mode == "Import reviews":
    render_import(niches, "review")
else:
    render_analysis_panel(niches)

st.divider()
st.subheader("Research library")
rows = [
    {"Niche": item.name, "Seed": item.seed_keyword, "Status": item.status.title(), "Updated": item.updated_at}
    for item in niches
]
if rows:
    st.dataframe(pd.DataFrame(rows), hide_index=True, key="research_library")
else:
    st.info("No niches have been created.")
