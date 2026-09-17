"""Dedicated opportunity report page."""

import streamlit as st

from db.database import session_scope
from db.repositories import NicheRepository
from ui.report_views import render_opportunity_report


st.caption("Select a niche to preview and download its latest evidence-linked Markdown report.")

with session_scope() as session:
    niches = NicheRepository(session).list_all()

if not niches:
    st.info("Create a niche and calculate a decision score before generating a report.")
    st.stop()

niches_by_id = {niche.id: niche for niche in niches}
niche_id = st.selectbox(
    "Niche",
    list(niches_by_id),
    format_func=lambda value: niches_by_id[value].name,
    key="report_niche",
    bind="query-params",
)
render_opportunity_report(niche_id, show_heading=False)
