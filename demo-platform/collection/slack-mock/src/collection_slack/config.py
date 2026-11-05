"""Server-side configuration. Nothing here is ever sent to the browser."""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import os
import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

MAX_MESSAGE_CHARS = 4000
MAX_BODY_BYTES = 16 * 1024

_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{3,128}$")
_REPO_RE = re.compile(r"^[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+$")


class ConfigError(ValueError):
    pass


def _is_loopback_host(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _scheme_ok(url: str) -> bool:
    parts = urlsplit(url)
    if not parts.hostname:
        return False
    return parts.scheme == "https" or (parts.scheme == "http" and _is_loopback_host(parts.hostname))


def _check_base_url(url: str) -> str:
    if not _scheme_ok(url):
        raise ConfigError("COLLECTION_DEVIN_API_BASE must be https (http only for loopback)")
    return url.rstrip("/")


@dataclass(frozen=True)
class AutomationRule:
    """Routes a matching message to the automation webhook instead of a direct session."""

    kind: str  # "mention" or "alert"
    channel: str | None
    pattern: re.Pattern[str] | None


@dataclass(frozen=True)
class Config:
    bind_host: str
    port: int
    db_path: str
    access_token: str = field(repr=False)
    cookie_secret: bytes = field(repr=False)
    mode: str  # "live" or "stub"
    devin_api_base: str
    devin_api_key: str | None = field(repr=False)
    devin_org_id: str | None
    create_as_user_id: str | None
    devin_mode: str
    repos: tuple[str, ...]
    max_acu_limit: int | None
    session_tags: tuple[str, ...]
    http_timeout: float
    poll_interval: float
    automation_url: str | None
    automation_secret: str | None = field(repr=False)
    automation_rules: tuple[AutomationRule, ...] = ()

    @property
    def live(self) -> bool:
        return self.mode == "live"

    @property
    def api_target(self) -> str:
        if not self.live:
            return "none"
        return "fake-loopback" if _is_loopback_host(urlsplit(self.devin_api_base).hostname or "") else "devin"

    @property
    def automation_enabled(self) -> bool:
        return bool(self.automation_url and self.automation_secret and self.automation_rules)


def _parse_rules(raw: str) -> tuple[AutomationRule, ...]:
    rules: list[AutomationRule] = []
    for item in filter(None, (r.strip() for r in raw.split(";"))):
        kind, _, rest = item.partition(":")
        channel, _, pattern = rest.partition(":")
        if kind not in ("mention", "alert"):
            raise ConfigError("COLLECTION_AUTOMATION_RULES entries must start with mention: or alert:")
        if kind == "alert" and not pattern:
            raise ConfigError("alert rules need a pattern: alert:<channel>:<regex>")
        rules.append(
            AutomationRule(
                kind=kind,
                channel=channel or None,
                pattern=re.compile(pattern, re.IGNORECASE) if pattern else None,
            )
        )
    return tuple(rules)


def _check_automation(url: str | None, allowed_host: str | None) -> str | None:
    if not url:
        return None
    parts = urlsplit(url)
    if not _scheme_ok(url):
        raise ConfigError("COLLECTION_AUTOMATION_URL must be https (http only for loopback)")
    if not allowed_host or (parts.hostname or "") != allowed_host.lower():
        raise ConfigError("COLLECTION_AUTOMATION_URL host is not COLLECTION_AUTOMATION_ALLOWED_HOST")
    if parts.username or parts.password or parts.query or parts.fragment:
        raise ConfigError("COLLECTION_AUTOMATION_URL must not carry credentials, query or fragment")
    return url


def load_config(env: dict[str, str] | None = None) -> Config:
    e = dict(os.environ if env is None else env)

    access_token = e.get("COLLECTION_ACCESS_TOKEN", "")
    if len(access_token) < 16:
        raise ConfigError("COLLECTION_ACCESS_TOKEN must be set (16+ chars)")

    api_key = e.get("DEVIN_API_KEY") or None
    org_id = e.get("COLLECTION_DEVIN_ORG_ID") or None
    user_id = e.get("COLLECTION_CREATE_AS_USER_ID") or None
    requested = e.get("COLLECTION_MODE", "stub").strip().lower()
    if requested not in ("stub", "live"):
        raise ConfigError("COLLECTION_MODE must be stub or live")
    if requested == "live":
        missing = [
            n
            for n, v in (
                ("DEVIN_API_KEY", api_key),
                ("COLLECTION_DEVIN_ORG_ID", org_id),
                ("COLLECTION_CREATE_AS_USER_ID", user_id),
            )
            if not v
        ]
        if missing:
            raise ConfigError("live mode needs " + ", ".join(missing))
        for name, value in (("COLLECTION_DEVIN_ORG_ID", org_id), ("COLLECTION_CREATE_AS_USER_ID", user_id)):
            if value is None or not _ID_RE.match(value):
                raise ConfigError(f"{name} has an unexpected format")

    repos = tuple(r.strip() for r in e.get("COLLECTION_REPOS", "").split(",") if r.strip())
    for r in repos:
        if not _REPO_RE.match(r):
            raise ConfigError("COLLECTION_REPOS must be owner/name entries")

    max_acu = e.get("COLLECTION_MAX_ACU_LIMIT", "")
    automation_url = _check_automation(
        e.get("COLLECTION_AUTOMATION_URL") or None, e.get("COLLECTION_AUTOMATION_ALLOWED_HOST") or None
    )

    return Config(
        bind_host=e.get("COLLECTION_BIND", "127.0.0.1"),
        port=int(e.get("COLLECTION_PORT", "8780")),
        db_path=e.get("COLLECTION_DB_PATH", "collection-slack.sqlite3"),
        access_token=access_token,
        cookie_secret=hmac.new(access_token.encode(), b"collection-slack-cookie", hashlib.sha256).digest(),
        mode=requested,
        devin_api_base=_check_base_url(e.get("COLLECTION_DEVIN_API_BASE", "https://api.devin.ai")),
        devin_api_key=api_key if requested == "live" else None,
        devin_org_id=org_id,
        create_as_user_id=user_id,
        devin_mode="fusion",
        repos=repos,
        max_acu_limit=int(max_acu) if max_acu else None,
        session_tags=tuple(t.strip() for t in e.get("COLLECTION_SESSION_TAGS", "collection-slack").split(",") if t.strip()),
        http_timeout=float(e.get("COLLECTION_HTTP_TIMEOUT", "10")),
        poll_interval=float(e.get("COLLECTION_POLL_INTERVAL", "5")),
        automation_url=automation_url,
        automation_secret=e.get("COLLECTION_AUTOMATION_SECRET") or None,
        automation_rules=_parse_rules(e.get("COLLECTION_AUTOMATION_RULES", "")),
    )
