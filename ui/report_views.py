"""Streamlit report preview and download controls."""

from __future__ import annotations

import streamlit as st

from db.database import session_scope
from services.report_service import generate_opportunity_report
from ui.layout import render_empty_state


def render_opportunity_report(niche_id: int, *, show_heading: bool = True) -> None:
    if show_heading:
        st.subheader("Opportunity report")
    st.caption("Preview and download a deterministic report generated from the latest score snapshot and its evidence references.")
    try:
        with session_scope() as session:
            report = generate_opportunity_report(session, niche_id=niche_id)
    except ValueError as exc:
        render_empty_state(
            title="No report available yet",
            body=str(exc),
            next_step="Open Niche detail, select Decision, and calculate a current score snapshot.",
            icon="description",
        )
        return

    if report.warnings:
        st.warning(
            f"This report contains {len(report.warnings)} evidence warning(s). Review them before using its recommendation.",
            title="Evidence requires review",
            icon=":material/warning:",
        )
    with st.container(horizontal=True):
        st.download_button(
            "Download Markdown report",
            data=report.markdown,
            file_name=report.file_name,
            mime="text/markdown",
            key=f"download_report_{niche_id}_{report.snapshot_id}",
            on_click="ignore",
            icon=":material/download:",
        )
        st.caption(f"Score snapshot S{report.snapshot_id} · {len(report.cited_review_ids)} cited reviews")

    with st.container(border=True):
        st.markdown(report.markdown)
