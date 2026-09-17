"""Dedicated evidence-grounded book specification page."""

import streamlit as st

from db.database import session_scope
from db.repositories import NicheRepository
from ui.concept_views import render_book_specification_view


with session_scope() as session:
    niches = NicheRepository(session).list_all()

if not niches:
    st.info("Create a niche and calculate a decision score before generating a book specification.")
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
