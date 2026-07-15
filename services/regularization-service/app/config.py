from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://attendance:attendance@postgres:5432/attendance_db"

    jwt_secret: str = "dev-only-change-me"  # must match identity-service
    jwt_algorithm: str = "HS256"

    attendance_service_url: str = "http://attendance-service:8000"
    attendance_service_api_key: str = "dev-local-api-key"  # must match attendance-service ATTENDANCE_API_KEY

    ai_agent_service_url: str = "http://ai-agent-service:8003"
    ai_agent_service_api_key: str = "dev-local-api-key"  # shared service key, same value across services in local dev

    class Config:
        env_file = ".env"
        env_prefix = "REGULARIZATION_"


settings = Settings()
