"""Streamlit workflow for starting a review-evidence analysis run."""

import streamlit as st

from config.settings import get_settings
from db.database import session_scope
from llm.base import ProviderContractError
from services.analysis_service import analyze_niche_reviews
from ui.errors import render_operation_error


def _analysis_error_message(error: BaseException) -> tuple[str, str, bool]:
    message = str(error)
    if isinstance(error, ValueError) and "OPENAI_API_KEY" in message:
        return (
            "OpenAI analysis is not configured.",
            "Add OPENAI_API_KEY to .env or select the mock provider, then try again.",
            True,
        )
    if isinstance(error, ValueError) and "no reviews" in message.lower():
        return (
            "This niche has no review evidence to analyze.",
            "Import reviews for the niche, then start analysis again.",
            True,
        )
    if isinstance(error, ProviderContractError):
        return (
            "The provider returned an analysis result the app could not validate.",
            "Previous evidence was preserved. Try again or switch to the deterministic mock provider.",
            True,
        )
    return (
        "Review analysis could not be completed.",
        "Previous evidence was preserved. Try again; use the error reference if the failure repeats.",
        False,
    )


def render_analysis_panel(niches: list[object]) -> None:
    st.subheader("Analyze review evidence")
    st.caption(
        "Extract pain points, praised features, desired outcomes, and evidence. "
        "Mock mode is deterministic and free; OpenAI is opt-in."
    )
    if not niches:
        st.info("Create a niche and import reviews before running analysis.")
        return
    by_id = {item.id: item for item in niches}
    settings = get_settings()
    with st.form("analysis_form"):
        niche_id = st.selectbox("Niche", list(by_id), format_func=lambda value: by_id[value].name)
        provider_name = st.radio("Provider", ("mock", "openai"), horizontal=True, index=0 if settings.llm_provider == "mock" else 1)
        batch_size = st.number_input("Reviews per batch", min_value=1, max_value=50, value=settings.llm_batch_size)
        force = st.checkbox("Force reanalysis", help="Ignore valid cached review results and analyze every review again.")
        submitted = st.form_submit_button("Analyze reviews", type="primary", icon=":material/psychology:")
    if not submitted:
        return

    status = st.status("Preparing analysis", expanded=True)
    bar = status.progress(0, text="Loading reviews")

    def update_progress(done: int, total: int, message: str) -> None:
        bar.progress(done / max(total, 1), text=message)

    try:
        with session_scope() as session:
            summary = analyze_niche_reviews(
                session,
                niche_id=niche_id,
                provider_name=provider_name,
                batch_size=int(batch_size),
                force=force,
                progress=update_progress,
            )
        bar.progress(1.0, text="Evidence saved")
        status.update(label=f"Analysis run {summary.run_id} completed", state="complete", expanded=False)
        st.session_state["phase3_analysis_flash"] = summary
        st.rerun()
    except Exception as exc:
        status.update(label="Analysis failed; previous evidence was preserved", state="error", expanded=True)
        summary, recovery, expected = _analysis_error_message(exc)
        render_operation_error(
            exc,
            operation="review_analysis.run",
            summary=summary,
            recovery=recovery,
            context={
                "niche_id": niche_id,
                "provider": provider_name,
            },
            expected=expected,
        )
