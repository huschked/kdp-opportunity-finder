from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest
from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session, sessionmaker
from streamlit.testing.v1 import AppTest

from config.logging import (
    REDACTED,
    configure_logging,
    log_operation_failure,
    reset_logging,
)
from config.settings import get_settings
from db.database import build_engine, initialize_database, session_scope
from models import Niche


ROOT = Path(__file__).resolve().parents[1]


def test_structured_failure_log_keeps_context_and_redacts_sensitive_values(
    tmp_path,
) -> None:
    log_path = tmp_path / "app.jsonl"
    secret = "sk-sensitive-value-123456"
    review_text = "This private review body must never be written to a log."
    configure_logging(log_path=log_path, console=False)

    try:
        raise RuntimeError(f"Provider failure {secret}: {review_text}")
    except RuntimeError as exc:
        reference = log_operation_failure(
            exc,
            operation="review_analysis.run",
            context={
                "niche_id": 17,
                "provider": "openai",
                "api_key": secret,
                "review_text": review_text,
            },
        )
    finally:
        reset_logging()

    raw_log = log_path.read_text(encoding="utf-8")
    payload = json.loads(raw_log)
    assert payload["event"] == "operation_failed"
    assert payload["operation"] == "review_analysis.run"
    assert payload["operation_id"] == reference
    assert payload["expected"] is False
    assert payload["exception_type"] == "RuntimeError"
    assert payload["context"] == {
        "niche_id": 17,
        "provider": "openai",
        "api_key": REDACTED,
        "review_text": REDACTED,
    }
    assert payload["traceback_frames"][-1]["function"].startswith(
        "test_structured_failure_log"
    )
    assert secret not in raw_log
    assert review_text not in raw_log


def test_streamlit_error_is_recovery_oriented_and_hides_raw_exception() -> None:
    app = AppTest.from_string(
        '''
from ui.errors import render_operation_error

try:
    raise RuntimeError("sk-hidden-value-123456 private review body")
except RuntimeError as exc:
    render_operation_error(
        exc,
        operation="export.render",
        summary="The export files could not be rendered.",
        recovery="No download was produced. Try again.",
        context={"export_type": "reviews"},
    )
'''
    ).run()

    assert not app.exception
    assert app.error[0].value == "The export files could not be rendered."
    assert "No download was produced. Try again." in app.caption[0].value
    assert "Error reference:" in app.caption[0].value
    visible = " ".join(
        [*(item.value for item in app.error), *(item.value for item in app.caption)]
    )
    assert "sk-hidden" not in visible
    assert "private review body" not in visible
    assert not app.success


def test_expected_failure_reference_is_logged_at_restrictive_level(tmp_path) -> None:
    log_path = tmp_path / "warnings.jsonl"
    configure_logging(log_path=log_path, level="ERROR", console=False)
    try:
        reference = log_operation_failure(
            ValueError("controlled validation failure"),
            operation="scoring.calculate",
            context={"niche_id": 4},
            expected=True,
        )
    finally:
        reset_logging()

    payload = json.loads(log_path.read_text(encoding="utf-8"))
    assert payload["operation_id"] == reference
    assert payload["level"] == "WARNING"
    assert payload["expected"] is True


def test_failed_transaction_rolls_back_without_creating_a_record(tmp_path) -> None:
    database_path = tmp_path / "rollback.db"
    engine = build_engine(f"sqlite:///{database_path.as_posix()}")
    initialize_database(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    with pytest.raises(RuntimeError, match="simulated write failure"):
        with session_scope(session_factory) as session:
            session.add(Niche(name="Must roll back", seed_keyword="rollback"))
            session.flush()
            raise RuntimeError("simulated write failure")

    with Session(engine) as session:
        assert session.scalar(select(func.count(Niche.id))) == 0


def test_real_app_contains_incompatible_schema_failure(monkeypatch, tmp_path) -> None:
    database_path = tmp_path / "partial.db"
    log_path = tmp_path / "schema_error.jsonl"
    partial_engine = build_engine(f"sqlite:///{database_path.as_posix()}")
    Niche.__table__.create(partial_engine)
    with Session(partial_engine) as session:
        session.add(Niche(name="Preserve me", seed_keyword="preserve"))
        session.commit()
    partial_engine.dispose()

    monkeypatch.setenv("KDP_DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    monkeypatch.setenv("KDP_LOG_PATH", str(log_path))
    get_settings.cache_clear()
    reset_logging()

    import db.database as database_module

    database_module.ENGINE.dispose()
    importlib.reload(database_module)
    try:
        app = AppTest.from_file(ROOT / "app.py", default_timeout=10).run()
        assert not app.exception
        assert app.error[0].value == (
            "The local database schema needs attention before the app can start."
        )
        assert "No schema changes were applied." in app.caption[0].value
        assert not app.success

        reset_logging()
        payload = json.loads(log_path.read_text(encoding="utf-8"))
        assert payload["level"] == "WARNING"
        assert payload["expected"] is True
        assert payload["operation"] == "startup.database_schema"
        assert payload["exception_type"] == "SchemaStateError"

        with Session(database_module.ENGINE) as session:
            assert session.scalar(select(func.count(Niche.id))) == 1
        assert "alembic_version" not in inspect(database_module.ENGINE).get_table_names()
    finally:
        reset_logging()
        database_module.ENGINE.dispose()
        monkeypatch.undo()
        get_settings.cache_clear()
        importlib.reload(database_module)
