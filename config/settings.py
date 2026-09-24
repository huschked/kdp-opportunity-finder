"""Environment-driven settings for the local application."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    llm_provider: str
    openai_model: str
    llm_batch_size: int
    openai_input_cost_per_million: float
    openai_output_cost_per_million: float
    scoring_config_path: Path
    log_level: str
    log_path: Path


def _project_path(environment_name: str, default: Path) -> Path:
    configured = Path(os.getenv(environment_name, str(default)))
    return configured if configured.is_absolute() else PROJECT_ROOT / configured


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv(
            "KDP_DATABASE_URL",
            f"sqlite:///{(PROJECT_ROOT / 'kdp_opportunity_finder.db').as_posix()}",
        ),
        llm_provider=os.getenv("KDP_LLM_PROVIDER", "mock"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        llm_batch_size=max(1, min(50, int(os.getenv("KDP_LLM_BATCH_SIZE", "20")))),
        openai_input_cost_per_million=float(os.getenv("OPENAI_INPUT_COST_PER_MILLION", "0")),
        openai_output_cost_per_million=float(os.getenv("OPENAI_OUTPUT_COST_PER_MILLION", "0")),
        scoring_config_path=PROJECT_ROOT / "config" / "scoring.yaml",
        log_level=os.getenv("KDP_LOG_LEVEL", "INFO").upper(),
        log_path=_project_path(
            "KDP_LOG_PATH",
            PROJECT_ROOT / "logs" / "kdp_opportunity_finder.jsonl",
        ),
    )
