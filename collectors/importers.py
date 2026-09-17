"""CSV/JSON/clipboard parsers with no persistence or marketplace coupling."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from io import StringIO
import json
from typing import Any


class DataFormatError(ValueError):
    """Raised when an uploaded document cannot be interpreted as records."""


@dataclass(frozen=True, slots=True)
class RawRecord:
    row_number: int
    values: Any


def parse_records(content: bytes, file_format: str, *, root_key: str) -> list[RawRecord]:
    normalized_format = file_format.lower().lstrip(".")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DataFormatError("File must be UTF-8 encoded") from exc

    if normalized_format == "csv":
        return _parse_csv(text)
    if normalized_format == "json":
        return _parse_json(text, root_key=root_key)
    raise DataFormatError(f"Unsupported file format: {file_format}")


def _parse_csv(text: str) -> list[RawRecord]:
    try:
        reader = csv.DictReader(StringIO(text))
        if not reader.fieldnames:
            raise DataFormatError("CSV must include a header row")
        fieldnames = [name.strip() if name else "" for name in reader.fieldnames]
        if not all(fieldnames):
            raise DataFormatError("CSV contains an empty column name")
        rows: list[RawRecord] = []
        for row_number, row in enumerate(reader, start=2):
            values = {
                (key.strip() if key else ""): value
                for key, value in row.items()
                if key is not None
            }
            rows.append(RawRecord(row_number=row_number, values=values))
        return rows
    except csv.Error as exc:
        raise DataFormatError(f"Invalid CSV: {exc}") from exc


def _parse_json(text: str, *, root_key: str) -> list[RawRecord]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DataFormatError(f"Invalid JSON at line {exc.lineno}: {exc.msg}") from exc

    if isinstance(payload, dict):
        if root_key not in payload:
            raise DataFormatError(
                f'JSON object must contain a "{root_key}" array, or the top level must be an array'
            )
        payload = payload[root_key]
    if not isinstance(payload, list):
        raise DataFormatError("JSON records must be an array")
    return [RawRecord(row_number=index, values=value) for index, value in enumerate(payload, start=1)]

