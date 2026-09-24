"""Dedicated evidence-grounded book specification page."""

import streamlit as st

from db.database import session_scope
from db.repositories import NicheRepository
from ui.concept_views import render_book_specification_view
from ui.layout import render_empty_state


with session_scope() as session:
    niches = NicheRepository(session).list_all()

if not niches:
    render_empty_state(
        title="No niche available for a specification",
        body="A specification draft requires a stored niche and its latest evidence-backed decision snapshot.",
        next_step="Create a niche in Research, collect evidence, and calculate a decision score.",
        icon="auto_stories",
    )
    st.stop()

niches_by_id = {niche.id: niche for niche in niches}
niche_id = st.selectbox(
    "Niche",
    list(niches_by_id),
    format_func=lambda value: niches_by_id[value].name,
    key="concept_niche",
    bind="query-params",
)
render_book_specification_view(niche_id)
