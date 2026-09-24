"""Configuration status page."""

import streamlit as st

from analysis.scoring import load_weights
from config.settings import get_settings


settings = get_settings()
st.caption("Configuration values are local. Secrets are never displayed here.")
st.table(
    {
        "Database": settings.database_url,
        "LLM provider": settings.llm_provider,
        "OpenAI model": settings.openai_model,
        "Scoring configuration": str(settings.scoring_config_path),
    },
    border="horizontal",
)
st.subheader("Active score weights", icon=":material/tune:")
weights = load_weights(settings.scoring_config_path)
st.table(
    {name.replace("_", " ").capitalize(): f"{weight:.0%}" for name, weight in weights.items()},
    border="horizontal",
)
st.info(
    "Weights and scoring targets are editable in config/scoring.yaml. "
    "Every new snapshot stores the exact policy and weights used, so earlier decisions remain auditable.",
    title="Immutable scoring policy",
    icon=":material/history:",
)
