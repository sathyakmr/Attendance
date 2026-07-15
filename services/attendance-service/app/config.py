"""
Centralized configuration. All values come from environment variables so the
same image runs unchanged across local Compose and (later) Kubernetes —
only the injected env differs.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://attendance:attendance@postgres:5432/attendance_db"

    # Debounce window: reject a second punch from the same employee within
    # this many seconds (guards against accidental double-taps / replay).
    debounce_seconds: int = 120

    # Soft shift-window validation: punches outside [shift_start - early, shift_end + late]
    # are stored but flagged rather than rejected outright — a human/AI agent
    # reviews flags later (see Section 6/8 of the design doc).
    early_checkin_grace_minutes: int = 30
    late_checkout_grace_minutes: int = 120

    # Geofence enforcement toggle — off by default for local dev where
    # synthetic lat/lng won't match seeded office coordinates.
    enforce_geofence: bool = False

    api_key: str = "dev-local-api-key"  # placeholder service-to-service auth; full RBAC service comes later

    ai_agent_service_url: str = "http://ai-agent-service:8003"

    class Config:
        env_file = ".env"
        env_prefix = "ATTENDANCE_"


settings = Settings()
