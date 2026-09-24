"""Streamlit entry point and shared application shell."""

from __future__ import annotations

import streamlit as st

from config.logging import configure_logging, log_event
from config.settings import get_settings
from db.database import initialize_database, session_scope
from db.migrations import SchemaStateError
from sample_data.generate import seed_sample_data
from ui.errors import render_operation_error


st.set_page_config(
    page_title="KDP Opportunity Finder",
    page_icon=":material/menu_book:",
    layout="wide",
)
settings = get_settings()
configure_logging(log_path=settings.log_path, level=settings.log_level)
try:
    migration = initialize_database()
except SchemaStateError as exc:
    render_operation_error(
        exc,
        operation="startup.database_schema",
        summary="The local database schema needs attention before the app can start.",
        recovery=(
            "No schema changes were applied. Stop the app, back up the database, "
            "and follow MIGRATIONS.md."
        ),
        expected=True,
    )
    st.stop()
except Exception as exc:
    render_operation_error(
        exc,
        operation="startup.database",
        summary="The app could not open or upgrade the local database.",
        recovery=(
            "Stop other processes using the database, confirm the configured path is writable, "
            "and try again."
        ),
    )
    st.stop()
else:
    if migration.action != "current":
        log_event(
            "database_schema_ready",
            operation="startup.database_schema",
            context={
                "migration_action": migration.action,
                "migration_revision": migration.current_revision,
            },
        )

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
        st.Page("app_pages/exports.py", title="Exports", icon=":material/download:"),
        st.Page("app_pages/settings.py", title="Settings", icon=":material/settings:"),
    ],
    position="sidebar",
)

with st.sidebar:
    st.caption("Sample workspace")
    if st.button("Load synthetic sample", width="stretch", icon=":material/database:"):
        try:
            with session_scope() as session:
                loaded = seed_sample_data(session)
        except Exception as exc:
            render_operation_error(
                exc,
                operation="sample_data.load",
                summary="The synthetic sample could not be loaded.",
                recovery="Existing research was not reported as replaced. Check the error reference and try again.",
            )
        else:
            if loaded:
                st.success("Loaded 3 niches, 30 books, and 180 synthetic reviews.")
                st.rerun()
            else:
                st.info("The database already contains research data; nothing was overwritten.")
    st.caption("Local SQLite · no scraper · mock LLM by default")

st.title(page.title, icon=page.icon)
try:
    page.run()
except Exception as exc:
    render_operation_error(
        exc,
        operation="page.render",
        summary="This page could not finish loading.",
        recovery="Refresh the page or choose another section. No failed operation was reported as successful.",
        context={"page": page.title},
    )
