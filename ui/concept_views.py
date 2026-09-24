"""Streamlit controls for book specification generation and review."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from db.database import session_scope
from db.repositories import ConceptRepository, ScoreRepository
from services.concept_service import generate_book_specification, render_book_specification
from ui.errors import render_operation_error


def render_book_specification_view(niche_id: int) -> None:
    st.caption(
        "Generate a local planning draft from stored pain points, praise, topics, outcomes, and the latest decision snapshot. No API call is made."
    )
    if st.button(
        "Generate new specification",
        type="primary",
        icon=":material/auto_stories:",
        key=f"generate_specification_{niche_id}",
    ):
        try:
            with session_scope() as session:
                generate_book_specification(session, niche_id=niche_id)
        except ValueError as exc:
            render_operation_error(
                exc,
                operation="book_specification.generate",
                summary="A new book specification was not created.",
                recovery="Calculate a current decision score and review required evidence, then try again.",
                context={"niche_id": niche_id},
                expected=True,
            )
        else:
            st.success("A new evidence-grounded specification snapshot was recorded.")
            st.rerun()

    with session_scope() as session:
        concepts = ConceptRepository(session)
        latest = concepts.latest_for_niche(niche_id)
        history = concepts.history_for_niche(niche_id)
        score = ScoreRepository(session).latest_for_niche(niche_id)

    if latest is None:
        st.info("No specification exists yet. Calculate a current decision score, then generate the first draft.")
        return

    artifact = render_book_specification(latest)
    if score is not None and score.id != artifact.snapshot_id:
        st.warning(
            f"A newer score snapshot exists (S{score.id}); this specification uses S{artifact.snapshot_id}. Generate a new specification before relying on it."
        )
    with st.container(horizontal=True):
        st.metric("Evidence-backed choices", artifact.evidence_backed_count, border=True)
        st.metric("Assumptions to validate", artifact.assumption_count, border=True)
        st.metric("Evidence warnings", artifact.warning_count, border=True)
        st.metric("Source snapshot", f"S{artifact.snapshot_id}", border=True)

    with st.container(horizontal=True):
        st.download_button(
            "Download Markdown specification",
            data=artifact.markdown,
            file_name=artifact.file_name,
            mime="text/markdown",
            key=f"download_specification_{niche_id}_{latest.id}",
            on_click="ignore",
            icon=":material/download:",
        )
        st.caption(f"Specification C{latest.id} · created {latest.created_at:%Y-%m-%d %H:%M}")

    with st.container(border=True):
        st.markdown(artifact.markdown)

    with st.expander(f"Specification history · {len(history)} drafts"):
        frame = pd.DataFrame([{
            "Concept": f"C{concept.id}",
            "Created": concept.created_at,
            "Working title": concept.title,
            "Score snapshot": f"S{concept.concept_json.get('source_snapshot_id')}",
            "Analysis run": concept.analysis_run_id,
            "Confidence": concept.concept_json.get("decision_context", {}).get("confidence"),
        } for concept in history])
        st.dataframe(frame, hide_index=True, key=f"concept_history_{niche_id}")
