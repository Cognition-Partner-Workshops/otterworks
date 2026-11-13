import hashlib
import re
from datetime import UTC, datetime, timedelta


def identifier(value):
    parts = value.split(".")
    if any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", p) for p in parts):
        raise ValueError("Invalid SQL identifier")
    return ".".join('"' + p + '"' for p in parts)


def token_name(token, prefix="MIGRATION"):
    if not re.fullmatch(r"[a-z][a-z0-9]{1,11}", token) or token == "main":
        raise ValueError("Token must be 2-12 lowercase letters/digits and cannot be main")
    if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,30}", prefix):
        raise ValueError("Invalid prefix")
    return f"{prefix}_{token.upper()}_AFTER"


def metadata(token, ttl_hours=24):
    token_name(token)
    if not 0 < ttl_hours <= 168:
        raise ValueError("TTL must be between 0 and 168 hours")
    expires = datetime.now(UTC) + timedelta(hours=ttl_hours)
    return {"token": token, "expires_at": expires.isoformat(timespec="seconds").replace("+00:00", "Z")}


def checksum(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def literal(value):
    return "'" + str(value).replace("\\", "\\\\").replace("'", "''") + "'"
