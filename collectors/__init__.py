"""Replaceable data-ingestion adapters."""

from collectors.importers import DataFormatError, RawRecord, parse_records

__all__ = ["DataFormatError", "RawRecord", "parse_records"]

