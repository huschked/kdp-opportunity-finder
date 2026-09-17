"""Evidence summaries, drill-down, and human grouping corrections."""

import pandas as pd
import streamlit as st

from db.database import session_scope
from db.repositories import EvidenceRepository
from services.evidence_service import merge_pain_points, rename_pain_point


def render_pain_points(niche_id: int) -> None:
    with session_scope() as session:
        rows = EvidenceRepository(session).pain_point_summaries(niche_id)
    st.subheader("Solvable reader pain points")
    st.caption("Shipping, seller, and buyer-mismatch complaints are excluded from opportunity totals.")
    if not rows:
        st.info("No solvable pain points yet. Run review analysis from Research.")
        return
    st.dataframe(
        pd.DataFrame([{
            "Pain point": row["name"], "Reviews": row["reviews"], "Books": row["books"],
            "Severity": row["severity"], "Solvability": row["solvability"], "Confidence": row["confidence"],
        } for row in rows]),
        hide_index=True,
        column_config={
            "Severity": st.column_config.NumberColumn(format="%.1f"),
            "Solvability": st.column_config.NumberColumn(format="%.1f"),
            "Confidence": st.column_config.NumberColumn(format="percent"),
        },
    )
    by_id = {row["id"]: row for row in rows}
    selected_id = st.selectbox("Inspect pain point", list(by_id), format_func=lambda value: by_id[value]["name"])
    selected = by_id[selected_id]
    with st.container(border=True):
        st.write(f"**{selected['name']}**")
        st.write(selected["description"] or "No description")
        st.caption(f"Suggested book response: {selected['solution'] or 'Not supplied'}")
    with session_scope() as session:
        evidence = EvidenceRepository(session).pain_point_evidence(selected_id)
    st.dataframe(pd.DataFrame(evidence), hide_index=True, column_config={"review": st.column_config.TextColumn(width="large")})

    with st.expander("Correct this grouping"):
        with st.form("rename_pain_point"):
            new_name = st.text_input("Canonical name", value=selected["name"])
            if st.form_submit_button("Rename"):
                try:
                    with session_scope() as session:
                        rename_pain_point(session, pain_point_id=selected_id, canonical_name=new_name)
                    st.success("Pain point renamed.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
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
                        st.error(str(exc))


def render_praise(niche_id: int) -> None:
    with session_scope() as session:
        rows = EvidenceRepository(session).praise_summaries(niche_id)
    st.subheader("Praised features and value signals")
    if not rows:
        st.info("No praised features yet. Run review analysis from Research.")
        return
    st.dataframe(
        pd.DataFrame([{
            "Praised feature": row["name"], "Reviews": row["reviews"], "Books": row["books"],
            "Strength": row["strength"], "Confidence": row["confidence"],
        } for row in rows]),
        hide_index=True,
        column_config={"Strength": st.column_config.NumberColumn(format="%.1f"), "Confidence": st.column_config.NumberColumn(format="percent")},
    )
    by_id = {row["id"]: row for row in rows}
    selected_id = st.selectbox("Inspect praised feature", list(by_id), format_func=lambda value: by_id[value]["name"])
    st.write(by_id[selected_id]["description"] or "No description")
    with session_scope() as session:
        evidence = EvidenceRepository(session).praise_evidence(selected_id)
    st.dataframe(pd.DataFrame(evidence), hide_index=True, column_config={"review": st.column_config.TextColumn(width="large")})


def render_analysis_history(niche_id: int) -> None:
    st.subheader("Analysis history")
    with session_scope() as session:
        rows = EvidenceRepository(session).analysis_runs(niche_id)
    if not rows:
        st.info("No analysis runs yet.")
        return
    st.dataframe(
        pd.DataFrame(rows),
        hide_index=True,
        column_config={
            "Started": st.column_config.DatetimeColumn(format="MMM DD, YYYY, h:mm a"),
            "Estimated cost": st.column_config.NumberColumn(format="dollar"),
        },
    )
