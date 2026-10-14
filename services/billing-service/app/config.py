from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "billing-service"
    mongodb_uri: str
    mongodb_database: str = "billing_migration"
    # JSON DSN of the legacy billing PostgreSQL (SELECT-only). Only the disposable
    # parity stack sets it; it feeds /internal/reset, which reloads the collections.
    source_dsn: str | None = None
    cors_origins: list[str] = ["http://localhost:3000"]
    allow_internal_reset: bool = False

    model_config = {"env_prefix": "BILLING_SVC_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
