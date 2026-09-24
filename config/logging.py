"""Structured local logging with narrow, explicit diagnostic context."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import re
import traceback
from typing import Any, Mapping
from uuid import uuid4


LOGGER_NAME = "kdp_opportunity_finder"
MAX_LOG_BYTES = 2_000_000
LOG_BACKUP_COUNT = 3
REDACTED = "[REDACTED]"
SAFE_CONTEXT_KEYS = {
    "action",
    "analysis_run_id",
    "batch_id",
    "book_id",
    "entity",
    "export_type",
    "migration_action",
    "migration_revision",
    "niche_id",
    "page",
    "provider",
    "record_count",
    "rejected_count",
    "score_snapshot_id",
    "status",
}
SENSITIVE_KEY_PARTS = (
    "api_key",
    "authorization",
    "body",
    "content",
    "password",
    "review_text",
    "secret",
    "token",
)
SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+\-/=]+"),
    re.compile(
        r"(?i)\b(openai_api_key|api[_-]?key|authorization|password|secret|token)"
        r"(\s*[:=]\s*)([^\s,;]+)"
    ),
)


def _redact_text(value: str) -> str:
    redacted = value
    for pattern in SECRET_PATTERNS:
        if pattern.groups == 3:
            redacted = pattern.sub(r"\1\2[REDACTED]", redacted)
        else:
            redacted = pattern.sub(REDACTED, redacted)
    return redacted[:500]


def _safe_context(context: Mapping[str, Any] | None) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in (context or {}).items():
        normalized_key = str(key).lower()
        if (
            normalized_key not in SAFE_CONTEXT_KEYS
            or any(part in normalized_key for part in SENSITIVE_KEY_PARTS)
        ):
            safe[normalized_key] = REDACTED
        elif value is None or isinstance(value, (bool, int, float)):
            safe[normalized_key] = value
        else:
            safe[normalized_key] = _redact_text(str(value))
    return safe


def _traceback_frames(error: BaseException) -> list[dict[str, Any]]:
    if error.__traceback__ is None:
        return []
    return [
        {
            "file": Path(frame.filename).name,
            "line": frame.lineno,
            "function": frame.name,
        }
        for frame in traceback.extract_tb(error.__traceback__)[-8:]
    ]


class JsonLineFormatter(logging.Formatter):
    """Render one redacted JSON object per log record."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": getattr(record, "event_name", "application_event"),
            "message": _redact_text(record.getMessage()),
        }
        for attribute in (
            "operation",
            "operation_id",
            "expected",
            "exception_type",
            "traceback_frames",
        ):
            value = getattr(record, attribute, None)
            if value not in (None, [], {}):
                payload[attribute] = value
        context = getattr(record, "safe_context", None)
        if context:
            payload["context"] = context
        return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


def get_application_logger(name: str | None = None) -> logging.Logger:
    suffix = f".{name}" if name else ""
    logger = logging.getLogger(f"{LOGGER_NAME}{suffix}")
    if not logging.getLogger(LOGGER_NAME).handlers:
        logging.getLogger(LOGGER_NAME).addHandler(logging.NullHandler())
    return logger


def configure_logging(
    *,
    log_path: Path,
    level: str = "INFO",
    console: bool = True,
) -> Path:
    """Configure idempotent rotating JSON-lines file and console handlers."""

    path = log_path.resolve()
    root_logger = logging.getLogger(LOGGER_NAME)
    resolved_level = getattr(logging, level.upper(), logging.INFO)
    signature = (str(path), level.upper(), console)
    if getattr(root_logger, "_kdp_logging_signature", None) == signature:
        root_logger.setLevel(min(resolved_level, logging.WARNING))
        root_logger.disabled = False
        root_logger.propagate = False
        return path

    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        handler.close()

    path.parent.mkdir(parents=True, exist_ok=True)
    formatter = JsonLineFormatter()
    file_handler = RotatingFileHandler(
        path,
        maxBytes=MAX_LOG_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    if console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    root_logger.setLevel(min(resolved_level, logging.WARNING))
    root_logger.disabled = False
    root_logger.propagate = False
    root_logger._kdp_logging_signature = signature  # type: ignore[attr-defined]
    return path


def reset_logging() -> None:
    """Close application handlers; primarily useful for isolated tests."""

    root_logger = logging.getLogger(LOGGER_NAME)
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        handler.close()
    if hasattr(root_logger, "_kdp_logging_signature"):
        del root_logger._kdp_logging_signature  # type: ignore[attr-defined]
    root_logger.addHandler(logging.NullHandler())


def log_event(
    event: str,
    *,
    operation: str,
    context: Mapping[str, Any] | None = None,
    level: int = logging.INFO,
) -> None:
    get_application_logger().log(
        level,
        "Application operation event",
        extra={
            "event_name": event,
            "operation": operation,
            "safe_context": _safe_context(context),
        },
    )


def log_operation_failure(
    error: BaseException,
    *,
    operation: str,
    context: Mapping[str, Any] | None = None,
    expected: bool = False,
    operation_id: str | None = None,
) -> str:
    """Log a failure without serializing the exception message or local values."""

    reference = operation_id or uuid4().hex[:12]
    get_application_logger().log(
        logging.WARNING if expected else logging.ERROR,
        "Application operation failed",
        extra={
            "event_name": "operation_failed",
            "operation": operation,
            "operation_id": reference,
            "expected": expected,
            "exception_type": type(error).__name__,
            "traceback_frames": _traceback_frames(error),
            "safe_context": _safe_context(context),
        },
    )
    return reference
