"""Decision-useful comparison of selected niche score snapshots."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from db.database import session_scope
from db.repositories import NicheRepository
from services.comparison_service import COMPONENT_LABELS, NicheComparisonRow, compare_niches
from ui.layout import render_empty_state


def _score_table(rows: tuple[NicheComparisonRow, ...]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Rank": row.rank,
                "Niche": row.niche_name,
                "Automated score": row.automated_score,
                "Human-adjusted score": row.human_adjusted_score,
                "Decision score": row.decision_score,
                "Confidence": row.confidence,
                "UDI": row.unmet_demand_index,
                "Recommendation": row.recommendation,
                "Warnings": row.warning_count,
                "Missing observations": row.missing_observation_count,
                "Snapshot": row.snapshot_id,
            }
            for row in rows
        ]
    )


def _coverage_table(rows: tuple[NicheComparisonRow, ...]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Niche": row.niche_name,
                "Competitor books": row.book_count,
                "Reviews": row.review_count,
                "Books with reviews": row.reviewed_book_count,
                "Field completeness": row.field_completeness,
                "Analysis coverage": row.analysis_completeness,
                "Evidence warnings": row.warning_count,
                "Snapshot calculated": row.calculated_at,
            }
            for row in rows
        ]
    )


def _render_score_chart(rows: tuple[NicheComparisonRow, ...]) -> None:
    scored = [row for row in rows if row.decision_score is not None and row.confidence is not None]
    if not scored:
        st.info("No selected niche has a score snapshot to chart.")
        return

    frame = pd.DataFrame(
        [
            {
                "Niche": row.niche_name,
                "Decision score": round(float(row.decision_score), 1),
                "Automated score": round(float(row.automated_score or 0), 1),
                "Human-adjusted score": (
                    round(float(row.human_adjusted_score), 1)
                    if row.human_adjusted_score is not None
                    else None
                ),
                "Confidence": round(float(row.confidence), 1),
                "Recommendation": row.recommendation,
                "Score source": "Human-adjusted" if row.human_adjusted_score is not None else "Automated",
            }
            for row in scored
        ]
    )
    points = (
        alt.Chart(frame)
        .mark_circle(size=180, opacity=0.85)
        .encode(
            x=alt.X("Decision score:Q", scale=alt.Scale(domain=[0, 100])),
            y=alt.Y("Confidence:Q", scale=alt.Scale(domain=[0, 100])),
            color=alt.Color("Niche:N", title="Niche"),
            shape=alt.Shape("Score source:N", title="Decision score source"),
            tooltip=[
                alt.Tooltip("Niche:N"),
                alt.Tooltip("Automated score:Q", format=".1f"),
                alt.Tooltip("Human-adjusted score:Q", format=".1f"),
                alt.Tooltip("Decision score:Q", format=".1f"),
                alt.Tooltip("Confidence:Q", format=".1f"),
                alt.Tooltip("Recommendation:N"),
            ],
        )
    )
    confidence_gate = (
        alt.Chart(pd.DataFrame({"Confidence": [60]}))
        .mark_rule(color="#888888", strokeDash=[6, 4])
        .encode(y="Confidence:Q")
    )
    st.altair_chart((confidence_gate + points).properties(height=340), width="stretch")
    st.caption(
        "The dashed line marks the 60-point confidence gate. Confidence does not increase the decision score; "
        "it limits recommendation language. Values are shown to one decimal place."
    )


def _render_component_chart(rows: tuple[NicheComparisonRow, ...]) -> None:
    component_rows = [
        {
            "Niche": row.niche_name,
            "Component": COMPONENT_LABELS[key],
            "Score": round(float(value), 1),
        }
        for row in rows
        for key, value in row.components.items()
        if value is not None
    ]
    if not component_rows:
        return
    frame = pd.DataFrame(component_rows)
    component_order = list(COMPONENT_LABELS.values())
    chart = (
        alt.Chart(frame)
        .mark_bar()
        .encode(
            x=alt.X("Score:Q", scale=alt.Scale(domain=[0, 100])),
            y=alt.Y("Component:N", sort=component_order),
            yOffset="Niche:N",
            color=alt.Color("Niche:N", title="Niche"),
            tooltip=[
                alt.Tooltip("Niche:N"),
                alt.Tooltip("Component:N"),
                alt.Tooltip("Score:Q", format=".1f"),
            ],
        )
        .properties(height=300)
    )
    st.altair_chart(chart, width="stretch")


st.caption(
    "Compare the latest immutable score snapshot for each selected niche. Rankings are descriptive and never "
    "replace evidence review or a publish decision."
)

with session_scope() as session:
    niches = NicheRepository(session).list_all()

if len(niches) < 2:
    render_empty_state(
        title="Comparison needs at least two niches",
        body="Each niche remains visible even when it has not been scored, so missing decision evidence is explicit.",
        next_step="Create another niche in Research, then return here to compare them.",
        icon="compare_arrows",
    )
    st.stop()

niche_names = {niche.id: niche.name for niche in niches}
default_ids = [niche.id for niche in niches[: min(4, len(niches))]]
selected_ids = st.multiselect(
    "Niches to compare",
    options=list(niche_names),
    default=default_ids,
    format_func=lambda niche_id: niche_names[niche_id],
    max_selections=6,
    placeholder="Choose two to six niches",
    key="comparison_niches",
    help="Comparison uses each niche's latest saved score snapshot; it does not silently recalculate scores.",
)

if len(selected_ids) < 2:
    render_empty_state(
        title="Select at least two niches",
        body="A side-by-side view requires two to six selected niches.",
        next_step="Choose one or more additional niches above.",
        icon="checklist",
    )
    st.stop()

with session_scope() as session:
    comparison = compare_niches(session, selected_ids)

st.subheader("Evidence comparability", icon=":material/fact_check:")
if comparison.coverage_warnings:
    st.warning("Review these limits before ranking:\n\n" + "\n".join(
        f"- {warning}" for warning in comparison.coverage_warnings
    ))
else:
    st.success("No material difference in stored evidence coverage was detected for these snapshots.")

with st.container(horizontal=True):
    st.metric("Selected niches", len(comparison.rows), border=True, icon=":material/topic:")
    st.metric("Scored niches", comparison.scored_count, border=True, icon=":material/query_stats:")
    st.metric(
        "Human adjustments",
        sum(row.human_adjusted_score is not None for row in comparison.rows),
        border=True,
        icon=":material/edit_note:",
    )
    st.metric(
        "Comparability alerts",
        len(comparison.coverage_warnings),
        border=True,
        icon=":material/warning:",
    )

st.subheader("Ranked decision view", icon=":material/leaderboard:")
st.caption(
    "Rows are ordered by the latest decision score. Unscored niches stay visible at the bottom, and ties use "
    "confidence only as a display-order tiebreaker."
)
st.dataframe(
    _score_table(comparison.rows),
    hide_index=True,
    key="comparison_score_table",
    column_config={
        "Rank": st.column_config.NumberColumn(format="%d", width="small"),
        "Niche": st.column_config.TextColumn(pinned=True),
        "Automated score": st.column_config.ProgressColumn(
            min_value=0, max_value=100, format="%.1f", color="blue"
        ),
        "Human-adjusted score": st.column_config.NumberColumn(format="%.1f"),
        "Decision score": st.column_config.NumberColumn(format="%.1f"),
        "Confidence": st.column_config.ProgressColumn(
            min_value=0, max_value=100, format="%.1f", color="auto"
        ),
        "UDI": st.column_config.NumberColumn(format="%.1f"),
        "Warnings": st.column_config.NumberColumn(format="%d"),
        "Missing observations": st.column_config.NumberColumn(format="%d"),
        "Snapshot": st.column_config.NumberColumn(format="%d"),
    },
)

st.subheader("Decision score and confidence", icon=":material/scatter_plot:")
_render_score_chart(comparison.rows)

st.subheader("Component differences", icon=":material/bar_chart:")
_render_component_chart(comparison.rows)

st.subheader("Evidence coverage", icon=":material/dataset:")
st.dataframe(
    _coverage_table(comparison.rows),
    hide_index=True,
    key="comparison_coverage_table",
    column_config={
        "Niche": st.column_config.TextColumn(pinned=True),
        "Competitor books": st.column_config.NumberColumn(format="%d"),
        "Reviews": st.column_config.NumberColumn(format="%d"),
        "Books with reviews": st.column_config.NumberColumn(format="%d"),
        "Field completeness": st.column_config.NumberColumn(format="percent"),
        "Analysis coverage": st.column_config.NumberColumn(format="percent"),
        "Evidence warnings": st.column_config.NumberColumn(format="%d"),
        "Snapshot calculated": st.column_config.DatetimeColumn(format="MMM DD, YYYY · h:mm a"),
    },
)

for row in comparison.rows:
    with st.expander(f"{row.niche_name} · evidence details"):
        if row.snapshot_id is None:
            st.info("No score snapshot exists. Calculate one from Niche detail before comparing this niche.")
            continue
        if row.warnings:
            st.markdown("**Evidence warnings**")
            st.markdown("\n".join(f"- {warning}" for warning in row.warnings))
        else:
            st.success("This snapshot contains no evidence warnings.")
        if row.missing_observations:
            st.markdown("**Missing component observations**")
            st.markdown("\n".join(f"- {item}" for item in row.missing_observations))
        else:
            st.caption("No component-level missing observations were recorded.")
        st.caption(
            f"Snapshot S{row.snapshot_id} · scoring version {row.scoring_version} · "
            f"calculated {row.calculated_at.isoformat() if row.calculated_at else 'unknown'}"
        )
