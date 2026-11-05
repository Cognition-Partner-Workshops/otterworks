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

    jwt_secret: str = field(default_factory=lambda: os.getenv("JWT_SECRET", ""))
    jwt_peer_secret: str = field(default_factory=lambda: os.getenv("JWT_PEER_SECRET", ""))
    service_token: str = field(
        default_factory=lambda: os.getenv("SEARCH_SERVICE_TOKEN", "")
    )
    require_auth: bool = field(
        default_factory=lambda: os.getenv("REQUIRE_AUTH", "true").lower() == "true"
    )


@dataclass(frozen=True)
class InsightsConfig:
    role: str = field(default_factory=lambda: os.getenv("SNOWFLAKE_ROLE", "SFEXT_20261105A_DOC_SEARCH_API_ENDPOINT"))
    user: str | None = field(default_factory=lambda: os.getenv("SNOWFLAKE_USER"))
    commit: str | None = field(default_factory=lambda: os.getenv("SF_COMMIT"))
    pool_size: int = field(default_factory=lambda: max(1, int(os.getenv("INSIGHTS_POOL_SIZE", "4"))))
    pool_timeout: float = field(default_factory=lambda: float(os.getenv("INSIGHTS_POOL_TIMEOUT", "5")))
    login_timeout: int = field(default_factory=lambda: int(os.getenv("INSIGHTS_LOGIN_TIMEOUT", "10")))
    network_timeout: int = field(default_factory=lambda: int(os.getenv("INSIGHTS_NETWORK_TIMEOUT", "15")))
    query_timeout: int = field(default_factory=lambda: int(os.getenv("INSIGHTS_QUERY_TIMEOUT", "20")))
    retries: int = field(default_factory=lambda: max(0, int(os.getenv("INSIGHTS_RETRIES", "2"))))
    backoff: float = field(default_factory=lambda: float(os.getenv("INSIGHTS_BACKOFF", "0.25")))


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
    insights: InsightsConfig = field(default_factory=InsightsConfig)
