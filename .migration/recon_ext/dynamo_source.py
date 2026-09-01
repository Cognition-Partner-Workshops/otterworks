"""D13: thin DynamoDB SourceAdapter extension for the official mongo-recon-harness.

Implements the harness `SourceAdapter` protocol over a LocalStack/AWS DynamoDB table so the
official engine, tiers, tolerances and report remain authoritative. Read-only (Scan with
ConsistentRead). Attribute values are typed from the mapping spec's `source_type` so the
harness sees the same native semantics a SQL adapter would (N -> int/Decimal,
S(iso8601) -> tz-aware datetime, BOOL -> bool, S -> str).

`root_where` supports the spec's form `attr = 'value'` (AND-chained), nothing else.
"""
from __future__ import annotations

import os
import re
from collections.abc import Iterable
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

_COND = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*'([^']*)'\s*$")


def _parse_where(where: str | None) -> dict[str, str]:
    if not where:
        return {}
    conds = {}
    for part in re.split(r"\s+AND\s+", where, flags=re.IGNORECASE):
        m = _COND.match(part)
        if not m:
            raise ValueError(f"unsupported DynamoDB where clause: {where!r}")
        conds[m.group(1)] = m.group(2)
    return conds


def _coerce(value: Any, source_type: str, bson_type: str) -> Any:
    if value is None:
        return None
    st = source_type.upper()
    if st == "N":
        d = value if isinstance(value, Decimal) else Decimal(str(value))
        return int(d) if bson_type in ("int", "long") else d
    if st.startswith("S(ISO8601)"):
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    if st == "BOOL":
        return bool(value)
    return str(value)


class DynamoSourceAdapter:
    def __init__(self, field_types: dict[str, dict[str, tuple[str, str]]],
                 endpoint_secret: str | None = None,
                 table_where: dict[str, str | None] | None = None):
        """field_types: {table: {attribute: (source_type, bson_type)}} from the mapping spec.
        endpoint_secret: ENV VAR NAME holding the endpoint URL (defaults to AWS_ENDPOINT_URL).
        table_where: {table: resolved root_where}; the protocol's key_strata receives no filter,
        so strata are drawn from this same partition rather than the whole table."""
        import boto3

        name = endpoint_secret or "AWS_ENDPOINT_URL"
        endpoint = os.environ.get(name)
        if not endpoint:
            raise RuntimeError(f"secret '{name}' not found in environment; pass secrets by name only")
        # LocalStack placeholder credentials only for a loopback endpoint; otherwise boto3's
        # own credential chain applies (fail closed, never silent test/test).
        loopback = endpoint.split("//", 1)[-1].split(":")[0] in ("localhost", "127.0.0.1")
        creds = {"aws_access_key_id": "test", "aws_secret_access_key": "test"} if loopback else {}
        self._ddb = boto3.resource("dynamodb", endpoint_url=endpoint,
                                   region_name=os.getenv("AWS_REGION", "us-east-1"), **creds)
        self._types = field_types
        self._where = table_where or {}
        self._cache: dict[tuple[str, str | None], list[dict[str, Any]]] = {}

    # -- scan (source concurrency 1: one serial consistent scan per table/where, cached) --
    def _items(self, table: str, where: str | None) -> list[dict[str, Any]]:
        key = (table, where)
        if key in self._cache:
            return self._cache[key]
        conds = _parse_where(where)
        kwargs: dict[str, Any] = {"ConsistentRead": True}
        if conds:
            names = {f"#a{i}": k for i, k in enumerate(conds)}
            values = {f":v{i}": v for i, v in enumerate(conds.values())}
            kwargs["FilterExpression"] = " AND ".join(
                f"#a{i} = :v{i}" for i in range(len(conds)))
            kwargs["ExpressionAttributeNames"] = names
            kwargs["ExpressionAttributeValues"] = values
        t = self._ddb.Table(table)
        types = self._types.get(table, {})
        out: list[dict[str, Any]] = []
        while True:
            resp = t.scan(**kwargs)
            for raw in resp.get("Items", []):
                out.append({k: _coerce(v, *types.get(k, ("S", "string"))) for k, v in raw.items()})
            if "LastEvaluatedKey" not in resp:
                break
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
        self._cache[key] = out
        return out

    def row_count(self, table: str, where: str | None = None) -> int:
        return len(self._items(table, where))

    def field_aggregates(self, table: str, column: str, where: str | None = None) -> dict[str, Any]:
        items = self._items(table, where)
        n = len(items)
        vals = [it[column] for it in items if it.get(column) is not None]
        numeric = bool(vals) and all(
            isinstance(v, (int, Decimal)) and not isinstance(v, bool) for v in vals)
        return {
            "count": n,
            "null_rate": (n - len(vals)) / n if n else 0.0,
            "min": min(vals) if vals else None,
            "max": max(vals) if vals else None,
            "distinct_count": len(set(vals)),
            "sum": sum(vals) if numeric else None,
        }

    def fetch_keyed(self, table: str, key_cols: list[str], columns: list[str],
                    where: str | None = None, keys: list[tuple] | None = None) -> Iterable[dict[str, Any]]:
        cols = list(dict.fromkeys(key_cols + columns))
        wanted = {tuple(k) for k in keys} if keys is not None else None
        rows = sorted(self._items(table, where), key=lambda it: tuple(it[k] for k in key_cols))
        for it in rows:
            if wanted is None or tuple(it[k] for k in key_cols) in wanted:
                yield {c: it.get(c) for c in cols}

    def key_strata(self, table: str, key_cols: list[str], n_strata: int) -> list[tuple]:
        keys = sorted({tuple(it[k] for k in key_cols)
                       for it in self._items(table, self._where.get(table))})
        if not keys or n_strata <= 0:
            return []
        step = max(1, len(keys) // n_strata)
        return keys[::step][:n_strata]
