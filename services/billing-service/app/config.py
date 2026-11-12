from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "billing-service"
    schema_name: str = "billing_svc"
    database_url: str
    cors_origins: list[str] = ["http://localhost:3000"]
    allow_internal_reset: bool = False
    auth_secret: SecretStr = Field(min_length=32)

    model_config = {"env_prefix": "BILLING_SVC_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
