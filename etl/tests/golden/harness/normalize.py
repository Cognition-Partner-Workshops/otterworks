"""The only rewrite applied to a snapshot before it is compared or stored.

Exactly two kinds of value are volatile across runs, and only these are
replaced with a placeholder; everything else is compared verbatim:

1. Report timestamps and durations inside S3 object bodies (JSON / JSON Lines):
   any value under a key in VOLATILE_BODY_KEYS. A timestamp is only replaced
   when it parses as ISO-8601 and a duration only when it is a number, so a
   malformed value still shows up as a diff.
2. Postgres columns the database fills with its own clock (NOW()), listed in
   VOLATILE_PG_COLUMNS. Same shape check: only ISO-8601 values are replaced.

The frozen clock already makes (1) stable for the legacy run; the placeholders
keep goldens comparable against a re-platformed run whose clock is not frozen.
"""

from __future__ import annotations

import copy
from datetime import datetime

TIMESTAMP_KEYS = frozenset({"generated_at"})
DURATION_KEYS = frozenset({"duration_seconds", "duration_ms"})
VOLATILE_BODY_KEYS = TIMESTAMP_KEYS | DURATION_KEYS
VOLATILE_PG_COLUMNS = frozenset({("analytics_daily_summary", "updated_at")})


def placeholder(name: str) -> str:
    return "<normalized:%s>" % name


def _is_iso_timestamp(value) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _is_duration(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _normalize_value(key: str, value):
    if key in TIMESTAMP_KEYS and _is_iso_timestamp(value):
        return placeholder(key), True
    if key in DURATION_KEYS and _is_duration(value):
        return placeholder(key), True
    return value, False


def _walk(node, counter: list[int]):
    if isinstance(node, dict):
        out = {}
        for key, value in node.items():
            new_value, changed = _normalize_value(key, value)
            if changed:
                counter[0] += 1
                out[key] = new_value
            else:
                out[key] = _walk(value, counter)
        return out
    if isinstance(node, list):
        return [_walk(item, counter) for item in node]
    return node


def normalize(files: dict[str, object]) -> tuple[dict[str, object], int]:
    """Return (normalized copy, number of values replaced)."""
    out = copy.deepcopy(files)
    counter = [0]
    for objects in out.get("s3.json", {}).values():
        for entry in objects.values():
            if entry.get("format") in ("json", "jsonl"):
                entry["body"] = _walk(entry["body"], counter)
    for table, data in out.get("postgres.json", {}).items():
        for row in data.get("rows", []):
            for column in row:
                if (table, column) in VOLATILE_PG_COLUMNS and _is_iso_timestamp(
                    row[column]
                ):
                    row[column] = placeholder(column)
                    counter[0] += 1
    return out, counter[0]
