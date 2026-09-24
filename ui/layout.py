"""Shared native Streamlit layout patterns for consistent page states."""

from __future__ import annotations

import streamlit as st


def render_empty_state(
    *,
    title: str,
    body: str,
    next_step: str,
    icon: str = "inbox",
) -> None:
    """Render an actionable, visually consistent empty state."""

    with st.container(border=True):
        st.info(body, title=title, icon=f":material/{icon}:")
        st.caption(f"Next step: {next_step}")
