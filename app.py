"""Streamlit entry point and shared application shell."""

from __future__ import annotations

import streamlit as st

from db.database import initialize_database, session_scope
from sample_data.generate import seed_sample_data


st.set_page_config(
    page_title="KDP Opportunity Finder",
    page_icon=":material/menu_book:",
    layout="wide",
)
initialize_database()

st.session_state.setdefault("selected_niche_id", None)

page = st.navigation(
    [
        st.Page("app_pages/dashboard.py", title="Dashboard", icon=":material/dashboard:", default=True),
        st.Page("app_pages/research.py", title="Research", icon=":material/science:"),
        st.Page("app_pages/niche_detail.py", title="Niche detail", icon=":material/menu_book:"),
        st.Page("app_pages/report.py", title="Opportunity report", icon=":material/description:"),
        st.Page("app_pages/concept.py", title="Book specification", icon=":material/auto_stories:"),
        st.Page("app_pages/compare.py", title="Compare", icon=":material/compare_arrows:"),
        st.Page("app_pages/pipeline.py", title="Pipeline", icon=":material/view_kanban:"),
        st.Page("app_pages/settings.py", title="Settings", icon=":material/settings:"),
    ],
    position="sidebar",
)

with st.sidebar:
    st.divider()
    if st.button("Load synthetic sample", width="stretch", icon=":material/database:"):
        with session_scope() as session:
            loaded = seed_sample_data(session)
        if loaded:
            st.success("Loaded 3 niches, 30 books, and 180 synthetic reviews.")
            st.rerun()
        else:
            st.info("The database already contains research data; nothing was overwritten.")
    st.caption("Local SQLite · no scraper · mock LLM by default")

st.title(page.title, icon=page.icon)
page.run()
