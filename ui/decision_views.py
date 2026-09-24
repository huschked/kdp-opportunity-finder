"""Streamlit rendering for inspectable Phase 4 decision scores."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from analysis.scoring import recommendation_label
from db.database import session_scope
from db.repositories import ScoreRepository
from services.scoring_service import apply_human_score_override, calculate_niche_score
from ui.errors import render_operation_error
from ui.layout import render_empty_state


COMPONENT_LABELS = {
    "demand": "Demand",
    "competition": "Competitive opportunity",
    "customer_gap": "Customer gap",
    "economics": "Economics",
    "ai_suitability": "AI suitability",
    "expansion": "Expansion",
}


def render_decision(niche_id: int) -> None:
    st.subheader("Decision score", icon=":material/query_stats:")
    st.caption("Calculate from the evidence currently stored for this niche. Missing facts reduce confidence and remain visible.")

    if st.button("Calculate a new snapshot", type="primary", icon=":material/calculate:", key=f"score_{niche_id}"):
        try:
            with session_scope() as session:
                calculate_niche_score(session, niche_id)
        except Exception as exc:
            render_operation_error(
                exc,
                operation="scoring.calculate",
                summary="A new score snapshot was not recorded.",
                recovery="Review the stored evidence and scoring configuration, then try again.",
                context={"niche_id": niche_id},
                expected=isinstance(exc, ValueError),
            )
            return
        else:
            st.success("A new automated score snapshot was recorded.")
            st.rerun()

    with session_scope() as session:
        repository = ScoreRepository(session)
        latest = repository.latest_for_niche(niche_id)
        history = repository.history_for_niche(niche_id)

    if latest is None:
        render_empty_state(
            title="No decision snapshot yet",
            body="A decision score uses only the evidence currently stored for this niche; missing observations remain visible.",
            next_step="Select Calculate a new snapshot above.",
            icon="query_stats",
        )
        return

    explanation = latest.explanation_json or {}
    automated_recommendation = str(explanation.get("recommendation", "Not available"))
    effective_score = latest.human_overall_score if latest.human_overall_score is not None else latest.automated_overall_score
    effective_recommendation = recommendation_label(effective_score, latest.confidence_score)
    with st.container(horizontal=True):
        st.metric("Decision score", f"{effective_score:.1f}", border=True, icon=":material/leaderboard:")
        st.metric("Automated score", f"{latest.automated_overall_score:.1f}", border=True, icon=":material/calculate:")
        st.metric(
            "Confidence",
            f"{latest.confidence_score:.1f}",
            border=True,
            icon=":material/fact_check:",
            help="Evidence coverage and quality. Confidence gates recommendation language but does not increase the score.",
        )
        st.metric(
            "Unmet demand index",
            f"{latest.unmet_demand_index or 0:.1f}",
            border=True,
            icon=":material/track_changes:",
            help="Demand, customer gap, solvability, and competitive accessibility combined multiplicatively.",
        )

    if effective_recommendation == "Needs more data":
        st.warning(
            "Opportunity language is gated until evidence confidence improves.",
            title=f"Recommendation: {effective_recommendation}",
            icon=":material/warning:",
        )
    else:
        st.success(
            "Review the supporting observations and warnings before making a publishing decision.",
            title=f"Recommendation: {effective_recommendation}",
            icon=":material/check_circle:",
        )
    if latest.human_overall_score is not None:
        st.caption(f"Automated recommendation: {automated_recommendation}. The displayed decision score includes a separately recorded human override.")

    confidence = explanation.get("confidence", {})
    warnings = confidence.get("warnings", [])
    if warnings:
        st.warning(
            "\n".join(f"- {warning}" for warning in warnings),
            title="Evidence warnings",
            icon=":material/warning:",
        )

    component_payload = explanation.get("components", {})
    rows = []
    for key, label in COMPONENT_LABELS.items():
        payload = component_payload.get(key, {})
        rows.append({
            "Component": label,
            "Score": float(payload.get("score", getattr(latest, f"{key}_score" if key != "competition" else "competition_score"))),
            "Weight": float((latest.weights_json or {}).get(key, 0)),
            "Observed factor weight": float(payload.get("observed_weight", 0)),
            "Missing": ", ".join(payload.get("missing", [])) or "None",
        })
    st.dataframe(
        pd.DataFrame(rows),
        hide_index=True,
        key=f"decision_components_{niche_id}_{latest.id}",
        column_config={
            "Score": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f"),
            "Weight": st.column_config.NumberColumn(format="percent"),
            "Observed factor weight": st.column_config.NumberColumn(format="percent"),
            "Component": st.column_config.TextColumn(pinned=True),
        },
    )

    st.subheader("Why the scores look this way", icon=":material/manage_search:")
    for key, label in COMPONENT_LABELS.items():
        payload = component_payload.get(key, {})
        with st.expander(
            f"{label} · {float(payload.get('score', 0)):.1f}",
            icon=":material/analytics:",
        ):
            st.write(payload.get("explanation", "No explanation was stored for this legacy snapshot."))
            if payload.get("calculation"):
                st.caption(payload["calculation"])
            factor_rows = [
                {"Factor": factor, "Normalized score": value}
                for factor, value in payload.get("factors", {}).items()
            ]
            if factor_rows:
                st.table(pd.DataFrame(factor_rows), border="horizontal")
            if payload.get("inputs"):
                st.json(payload["inputs"], expanded=False)
            if payload.get("missing"):
                st.info(
                    ", ".join(payload["missing"]),
                    title="Missing observations",
                    icon=":material/help:",
                )

    udi = explanation.get("udi", {})
    with st.expander("Unmet demand index factors", icon=":material/track_changes:"):
        st.write(udi.get("explanation", "No UDI explanation was stored for this legacy snapshot."))
        if udi.get("factors"):
            st.table(pd.DataFrame([
                {"Factor": factor.title(), "Score": value}
                for factor, value in udi["factors"].items()
            ]), border="horizontal")

    st.subheader("Human decision adjustment", icon=":material/edit_note:")
    st.caption("An adjustment creates a new snapshot. It does not alter the automated components or confidence score.")
    with st.form(f"human_override_{niche_id}"):
        human_score = st.number_input(
            "Human decision score",
            min_value=0.0,
            max_value=100.0,
            value=float(effective_score),
            step=0.5,
        )
        rationale = st.text_area("Rationale", placeholder="Record the evidence or business constraint behind this adjustment.")
        submitted = st.form_submit_button("Record adjustment", icon=":material/edit_note:")
    if submitted:
        try:
            with session_scope() as session:
                apply_human_score_override(
                    session,
                    niche_id=niche_id,
                    human_score=float(human_score),
                    rationale=rationale,
                )
        except ValueError as exc:
            render_operation_error(
                exc,
                operation="scoring.human_override",
                summary="The human adjustment was not recorded.",
                recovery="Enter a score from 0 to 100 and a rationale, then try again.",
                context={"niche_id": niche_id},
                expected=True,
            )
        else:
            st.success("The human adjustment was recorded without changing the automated score.")
            st.rerun()

    with st.expander(
        f"Score history · {len(history)} snapshots",
        icon=":material/history:",
    ):
        history_rows = [{
            "Calculated": item.calculated_at,
            "Version": item.scoring_version,
            "Automated": item.automated_overall_score,
            "Human": item.human_overall_score,
            "Confidence": item.confidence_score,
            "UDI": item.unmet_demand_index,
            "Automated recommendation": (item.explanation_json or {}).get("recommendation", "Not available"),
            "Decision recommendation": recommendation_label(
                item.human_overall_score if item.human_overall_score is not None else item.automated_overall_score,
                item.confidence_score,
            ),
            "Override rationale": ((item.explanation_json or {}).get("human_override") or {}).get("rationale"),
        } for item in history]
        st.dataframe(pd.DataFrame(history_rows), hide_index=True, key=f"score_history_{niche_id}")
