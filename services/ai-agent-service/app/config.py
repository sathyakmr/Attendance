from pathlib import Path

import yaml
from pydantic_settings import BaseSettings

POLICIES_DIR = Path(__file__).resolve().parent.parent / "policies"


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://attendance:attendance@postgres:5432/attendance_db"

    jwt_secret: str = "dev-only-change-me"  # must match identity-service
    jwt_algorithm: str = "HS256"

    attendance_service_url: str = "http://attendance-service:8000"
    attendance_service_api_key: str = "dev-local-api-key"

    # Optional. If unset, the agent runs in fully deterministic mode — every
    # decision is still made, just without LLM-generated narrative/phrasing.
    # This is the "deterministic fallback" required by the design doc
    # (Section 6/9.3): the agent must keep functioning if the LLM is down
    # or simply not configured for this environment.
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    llm_timeout_seconds: float = 15.0

    class Config:
        env_file = ".env"
        env_prefix = "AI_AGENT_"


settings = Settings()


def _load_yaml(filename: str) -> dict:
    with open(POLICIES_DIR / filename) as f:
        return yaml.safe_load(f)


POLICY = _load_yaml("thresholds.yaml")


def load_policy_doc_text() -> str:
    with open(POLICIES_DIR / "attendance_policy.md") as f:
        return f.read()
