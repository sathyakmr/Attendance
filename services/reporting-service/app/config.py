from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://attendance:attendance@postgres:5432/attendance_db"

    attendance_service_url: str = "http://attendance-service:8000"
    attendance_service_api_key: str = "dev-local-api-key"

    ai_agent_service_url: str = "http://ai-agent-service:8003"
    ai_agent_service_api_key: str = "dev-local-api-key"

    # --- WhatsApp Business Cloud API ---
    # All optional. If whatsapp_access_token is unset, the client runs in
    # MOCK mode: it logs what would have been sent, synthesizes a fake
    # wamid, and returns success — so the full report -> notification ->
    # retry -> delivery-status pipeline is testable with zero external
    # credentials, exactly like the ai-agent-service's LLM fallback in
    # Phase 3.
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_to_number: str = ""  # the business owner's WhatsApp number, E.164 format
    whatsapp_api_version: str = "v20.0"
    whatsapp_template_name: str = "attendance_report"  # must be pre-approved in WhatsApp Business Manager
    whatsapp_app_secret: str = ""  # for verifying inbound webhook signatures (X-Hub-Signature-256)
    whatsapp_webhook_verify_token: str = "dev-local-verify-token"  # for the GET verification handshake

    # --- Retry policy ---
    max_send_attempts: int = 3
    retry_backoff_base_seconds: float = 2.0

    # --- Scheduler ---
    # Cron expressions (APScheduler format). Defaults: daily at 18:00,
    # weekly Monday 09:00, monthly 1st at 09:00. Override via env for demos.
    daily_report_cron: str = "0 18 * * *"
    weekly_report_cron: str = "0 9 * * 1"
    monthly_report_cron: str = "0 9 1 * *"
    scheduler_enabled: bool = True

    class Config:
        env_file = ".env"
        env_prefix = "REPORTING_"


settings = Settings()
