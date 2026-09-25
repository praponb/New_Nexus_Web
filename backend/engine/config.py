"""Engine configuration, read once from Django settings / environment."""

from __future__ import annotations

import os
from dataclasses import dataclass

from django.conf import settings


# Secrets and platform wiring that agent subprocesses (the harness, QA's run_command, generated
# apps) must never inherit: the model key, and settings that would point a generated Django app at
# Nexus's own database. The harness merges os.environ into its child env, so they are removed
# from the process environment once Django is configured and kept here for the engine's own use.
SCRUBBED_ENV_VARS = (
    "MODEL_API_KEY",
    "DJANGO_SETTINGS_MODULE",
    "DJANGO_SECRET_KEY",
    "DB_ENGINE",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "DATABASE_URL",
    "REDIS_URL",
    "CELERY_BROKER_URL",
    "CELERY_RESULT_BACKEND",
    "CHANNEL_LAYER",
)
_scrubbed: dict[str, str] = {}


def scrub_process_env() -> list[str]:
    """Remove SCRUBBED_ENV_VARS from os.environ (idempotent); returns the names removed."""
    removed = []
    for key in SCRUBBED_ENV_VARS:
        if key in os.environ:
            _scrubbed[key] = os.environ.pop(key)
            removed.append(key)
    return removed


def env_value(key: str, default: str = "") -> str:
    return os.environ.get(key) or _scrubbed.get(key, default)


@dataclass(frozen=True)
class EngineConfig:
    mode: str  # "mock" | "live"
    model_name: str
    api_base: str
    api_key: str
    reasoning_effort: str
    max_qa_iterations: int
    retry_attempts: int = 4
    retry_initial_backoff: float = 70.0

    @property
    def is_live(self) -> bool:
        return self.mode == "live"

    def __repr__(self) -> str:  # never leak the key into logs
        return f"EngineConfig(mode={self.mode!r}, model_name={self.model_name!r}, api_base={self.api_base!r})"


def load_config() -> EngineConfig:
    return EngineConfig(
        mode=getattr(settings, "NEXUS_ENGINE_MODE", "mock"),
        model_name=env_value("MODEL_NAME", "kimi-k3"),
        api_base=env_value("MODEL_API_BASE", "https://api.moonshot.ai/v1").rstrip("/"),
        api_key=env_value("MODEL_API_KEY"),
        reasoning_effort=os.environ.get("MODEL_REASONING_EFFORT", ""),
        max_qa_iterations=int(getattr(settings, "NEXUS_MAX_QA_ITERATIONS", 3)),
        retry_attempts=int(os.environ.get("NEXUS_RETRY_ATTEMPTS", "4")),
        retry_initial_backoff=float(os.environ.get("NEXUS_RETRY_BACKOFF_SECONDS", "70")),
    )
