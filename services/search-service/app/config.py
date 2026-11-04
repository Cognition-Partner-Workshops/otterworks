"""Configuration for the Search Service."""

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class MeiliSearchConfig:
    """MeiliSearch connection configuration."""

    url: str = field(default_factory=lambda: os.getenv("MEILISEARCH_URL", "http://localhost:7700"))
    api_key: str = field(default_factory=lambda: os.getenv("MEILISEARCH_API_KEY", ""))
    documents_index: str = field(
        default_factory=lambda: os.getenv("MEILISEARCH_DOCUMENTS_INDEX", "documents")
    )
    files_index: str = field(
        default_factory=lambda: os.getenv("MEILISEARCH_FILES_INDEX", "files")
    )


@dataclass(frozen=True)
class SQSConfig:
    """SQS consumer configuration."""

    queue_url: str = field(default_factory=lambda: os.getenv("SQS_QUEUE_URL", ""))
    region: str = field(default_factory=lambda: os.getenv("AWS_REGION", "us-east-1"))
    endpoint_url: str = field(default_factory=lambda: os.getenv("AWS_ENDPOINT_URL", ""))
    max_messages: int = 10
    wait_time_seconds: int = 20
    visibility_timeout: int = 60
    enabled: bool = field(
        default_factory=lambda: os.getenv("SQS_ENABLED", "false").lower() == "true"
    )


@dataclass(frozen=True)
class AuthConfig:
    """Authentication configuration for the search service."""

    service_token: str = field(
        default_factory=lambda: os.getenv("SEARCH_SERVICE_TOKEN", "")
    )
    require_auth: bool = field(
        default_factory=lambda: os.getenv("REQUIRE_AUTH", "true").lower() == "true"
    )


@dataclass(frozen=True)
class SnowflakeConfig:
    """Snowflake connection and query settings for search insights."""

    account: str = field(default_factory=lambda: os.getenv("SNOWFLAKE_ACCOUNT", ""))
    private_key_file: str = field(default_factory=lambda: os.getenv("SNOWFLAKE_PRIVATE_KEY_FILE", ""))
    private_key_file_pwd: str | None = field(
        default_factory=lambda: os.getenv("SNOWFLAKE_PRIVATE_KEY_FILE_PWD") or None
    )
    role: str = field(default_factory=lambda: os.getenv("SNOWFLAKE_ROLE", "SFNFR_20261104_READER"))
    deployed_commit: str = field(default_factory=lambda: os.getenv("DEPLOYED_COMMIT", ""))
    query_phase: str = field(default_factory=lambda: os.getenv("SNOWFLAKE_QUERY_PHASE", "runtime"))
    session_url: str = field(default_factory=lambda: os.getenv("SESSION_URL", ""))
    pool_size: int = field(default_factory=lambda: int(os.getenv("SNOWFLAKE_POOL_SIZE", "4")))
    login_timeout: int = field(default_factory=lambda: int(os.getenv("SNOWFLAKE_LOGIN_TIMEOUT", "10")))
    network_timeout: int = field(default_factory=lambda: int(os.getenv("SNOWFLAKE_NETWORK_TIMEOUT", "30")))
    query_timeout: int = field(default_factory=lambda: int(os.getenv("SNOWFLAKE_QUERY_TIMEOUT", "15")))
    max_retries: int = field(default_factory=lambda: int(os.getenv("SNOWFLAKE_MAX_RETRIES", "3")))
    backoff_base: float = field(default_factory=lambda: float(os.getenv("SNOWFLAKE_BACKOFF_BASE", "0.2")))
    backoff_max: float = field(default_factory=lambda: float(os.getenv("SNOWFLAKE_BACKOFF_MAX", "2.0")))

    def validate(self) -> None:
        if self.account:
            import re

            if not re.fullmatch(r"[0-9a-f]{40}", self.deployed_commit):
                raise ValueError("DEPLOYED_COMMIT must be a 40-character lowercase SHA when Snowflake is configured")
            if self.query_phase not in {"dev", "runtime"}:
                raise ValueError("SNOWFLAKE_QUERY_PHASE must be dev or runtime")
            if self.query_phase == "dev" and not self.session_url:
                raise ValueError("SESSION_URL is required for a dev Snowflake query phase")


@dataclass(frozen=True)
class AppConfig:
    """Top-level application configuration."""

    service_name: str = "search-service"
    host: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8087")))
    debug: bool = field(
        default_factory=lambda: os.getenv("FLASK_DEBUG", "false").lower() == "true"
    )
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    meilisearch: MeiliSearchConfig = field(default_factory=MeiliSearchConfig)
    sqs: SQSConfig = field(default_factory=SQSConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)
    snowflake: SnowflakeConfig = field(default_factory=SnowflakeConfig)
