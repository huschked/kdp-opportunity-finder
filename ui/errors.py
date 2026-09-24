"""Consistent, safe Streamlit error presentation."""

from __future__ import annotations

from typing import Any, Mapping

import streamlit as st

from config.logging import log_operation_failure


def render_operation_error(
    error: BaseException,
    *,
    operation: str,
    summary: str,
    recovery: str,
    context: Mapping[str, Any] | None = None,
    expected: bool = False,
) -> str:
    """Log safe diagnostics and render a recovery-oriented message."""

    reference = log_operation_failure(
        error,
        operation=operation,
        context=context,
        expected=expected,
    )
    st.error(summary, icon=":material/error:")
    st.caption(f"{recovery} Error reference: `{reference}`")
    return reference
