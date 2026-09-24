"""Evidence summaries, drill-down, and human grouping corrections."""

import pandas as pd
import streamlit as st

from db.database import session_scope
from db.repositories import EvidenceRepository
from services.evidence_service import merge_pain_points, rename_pain_point
from ui.errors import render_operation_error
from ui.layout import render_empty_state


def render_pain_points(niche_id: int) -> None:
    with session_scope() as session:
        rows = EvidenceRepository(session).pain_point_summaries(niche_id)
    st.subheader("Solvable reader pain points", icon=":material/problem:")
    st.caption("Shipping, seller, and buyer-mismatch complaints are excluded from opportunity totals.")
    if not rows:
        render_empty_state(
            title="No solvable reader pain points yet",
            body="Logistics, seller, and buyer-mismatch complaints remain traceable but are excluded from opportunity totals.",
            next_step="Import source reviews and run Analyze reviews from Research.",
            icon="problem",
        )
        return
    st.dataframe(
        pd.DataFrame([{
            "Pain point": row["name"], "Reviews": row["reviews"], "Books": row["books"],
            "Severity": row["severity"], "Solvability": row["solvability"], "Confidence": row["confidence"],
        } for row in rows]),
        hide_index=True,
        column_config={
            "Pain point": st.column_config.TextColumn(pinned=True),
            "Severity": st.column_config.NumberColumn(format="%.1f"),
            "Solvability": st.column_config.NumberColumn(format="%.1f"),
            "Confidence": st.column_config.NumberColumn(format="percent"),
        },
    )
    by_id = {row["id"]: row for row in rows}
    selected_id = st.selectbox(
        "Inspect pain point",
        list(by_id),
        format_func=lambda value: by_id[value]["name"],
        key=f"pain_point_{niche_id}",
    )
    selected = by_id[selected_id]
    with st.container(border=True):
        st.write(f"**{selected['name']}**")
        st.write(selected["description"] or "No description")
        st.caption(f"Suggested book response: {selected['solution'] or 'Not supplied'}")
    with session_scope() as session:
        evidence = EvidenceRepository(session).pain_point_evidence(selected_id)
    st.dataframe(
        pd.DataFrame(evidence),
        hide_index=True,
        key=f"pain_evidence_{selected_id}",
        column_config={"review": st.column_config.TextColumn(width="large")},
    )

    with st.expander("Correct this grouping", icon=":material/edit:"):
        with st.form("rename_pain_point"):
            new_name = st.text_input("Canonical name", value=selected["name"])
            if st.form_submit_button("Rename"):
                try:
                    with session_scope() as session:
                        rename_pain_point(session, pain_point_id=selected_id, canonical_name=new_name)
                    st.success("Pain point renamed.")
                    st.rerun()
                except ValueError as exc:
                    render_operation_error(
                        exc,
                        operation="evidence.pain_point_rename",
                        summary="The pain-point group was not renamed.",
                        recovery="Use a non-empty unique name, then try again.",
                        context={"niche_id": niche_id},
                        expected=True,
                    )
        if len(rows) > 1:
            targets = [row["id"] for row in rows if row["id"] != selected_id]
            with st.form("merge_pain_point"):
                target_id = st.selectbox("Merge into", targets, format_func=lambda value: by_id[value]["name"])
                if st.form_submit_button("Merge groups"):
                    try:
                        with session_scope() as session:
                            merge_pain_points(session, source_id=selected_id, target_id=target_id)
                        st.success("Pain-point groups merged.")
                        st.rerun()
                    except ValueError as exc:
                        render_operation_error(
                            exc,
                            operation="evidence.pain_point_merge",
                            summary="The pain-point groups were not merged.",
                            recovery="Choose two different groups from the same niche, then try again.",
                            context={"niche_id": niche_id},
                            expected=True,
                        )


def render_praise(niche_id: int) -> None:
    with session_scope() as session:
        rows = EvidenceRepository(session).praise_summaries(niche_id)
    st.subheader("Praised features and value signals", icon=":material/thumb_up:")
    if not rows:
        render_empty_state(
            title="No praised features yet",
            body="Praised features appear only when stored source reviews support them.",
            next_step="Import source reviews and run Analyze reviews from Research.",
            icon="thumb_up",
        )
        return
    st.dataframe(
        pd.DataFrame([{
            "Praised feature": row["name"], "Reviews": row["reviews"], "Books": row["books"],
            "Strength": row["strength"], "Confidence": row["confidence"],
        } for row in rows]),
        hide_index=True,
        column_config={
            "Praised feature": st.column_config.TextColumn(pinned=True),
            "Strength": st.column_config.NumberColumn(format="%.1f"),
            "Confidence": st.column_config.NumberColumn(format="percent"),
        },
    )
    by_id = {row["id"]: row for row in rows}
    selected_id = st.selectbox(
        "Inspect praised feature",
        list(by_id),
        format_func=lambda value: by_id[value]["name"],
        key=f"praise_feature_{niche_id}",
    )
    with st.container(border=True):
        st.write(f"**{by_id[selected_id]['name']}**")
        st.write(by_id[selected_id]["description"] or "No description supplied.")
    with session_scope() as session:
        evidence = EvidenceRepository(session).praise_evidence(selected_id)
    st.dataframe(
        pd.DataFrame(evidence),
        hide_index=True,
        key=f"praise_evidence_{selected_id}",
        column_config={"review": st.column_config.TextColumn(width="large")},
    )


def render_analysis_history(niche_id: int) -> None:
    st.subheader("Analysis history", icon=":material/history:")
    with session_scope() as session:
        rows = EvidenceRepository(session).analysis_runs(niche_id)
    if not rows:
        render_empty_state(
            title="No analysis runs yet",
            body="Completed and failed runs appear here with provider, model, timing, token, and cost metadata.",
            next_step="Open Research and run Analyze reviews for this niche.",
            icon="history",
        )
        return
    st.dataframe(
        pd.DataFrame(rows),
        hide_index=True,
        key=f"analysis_history_{niche_id}",
        column_config={
            "Started": st.column_config.DatetimeColumn(format="MMM DD, YYYY, h:mm a"),
            "Estimated cost": st.column_config.NumberColumn(format="dollar"),
        },
    )
