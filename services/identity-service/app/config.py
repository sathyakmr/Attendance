from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://attendance:attendance@postgres:5432/attendance_db"

    # Shared secret across identity-service and any service that verifies
    # JWTs issued here (e.g. regularization-service). In cloud deployment
    # this moves to the secrets manager, never an env default like this.
    jwt_secret: str = "dev-only-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 60

    class Config:
        env_file = ".env"
        env_prefix = "IDENTITY_"


settings = Settings()
