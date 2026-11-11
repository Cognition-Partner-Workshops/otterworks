"""Application configuration via pydantic-settings."""

from pydantic import model_validator
from pydantic_settings import BaseSettings
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    app_name: str = "document-service"
    app_version: str = "0.1.0"
    debug: bool = False

    database_url: str = "postgresql+asyncpg://otterworks@localhost:5432/otterworks"
    db_password: str = ""
    db_pool_size: int = 10
    db_max_overflow: int = 20

    sns_topic_arn: str = ""
    aws_endpoint_url: str = ""
    aws_region: str = "us-east-1"
    sns_enabled: bool = False

    otel_exporter_otlp_endpoint: str = "http://localhost:4318"
    otel_enabled: bool = False

    request_log_dir: str = "/var/log/otterworks/document-service"

    rollup_enabled: bool = True
    rollup_interval_seconds: int = 60

    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:4200"]

    model_config = {"env_prefix": "DOC_SVC_", "env_file": ".env", "extra": "ignore"}

    @model_validator(mode="after")
    def _apply_db_password(self) -> "Settings":
        if self.db_password:
            url = make_url(self.database_url).set(password=self.db_password)
            self.database_url = url.render_as_string(hide_password=False)
        return self


settings = Settings()
