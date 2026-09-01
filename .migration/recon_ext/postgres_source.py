"""PostgresSourceAdapter: harness `SourceAdapter` protocol over psycopg 3 (D13).

Read-only. The DSN is read from the environment variable NAMED by `dsn_secret`; the value
is never logged. Type handling that keeps the harness's comparisons meaningful:

- uuid columns are returned as lowercase strings (so keyed lookups against the target's
  string `_id`/element keys match; the profile's `uuid_normalize` rule is a no-op on them),
- MIN/MAX on text-like columns use `COLLATE "C"` (byte order, matching MongoDB's binary
  string comparison rather than the database's en_US collation),
- MIN/MAX on boolean columns go through `::int` (Postgres has no min(boolean)),
- SUM is attempted and reported as null when the type has no sum (numeric-only, as the
  harness's Oracle/SQL Server adapters do).
"""

from __future__ import annotations

import os
from typing import Any, Iterable

import psycopg
from psycopg import sql
from psycopg.adapt import Loader
from psycopg.postgres import types as pg_types

_TEXT_TYPES = {"text", "character varying", "character", "varchar", "bpchar", "name", "uuid"}
_BOOL_TYPES = {"boolean", "bool"}


class _UuidTextLoader(Loader):
    def load(self, data: bytes | bytearray | memoryview) -> str:
        return bytes(data).decode("ascii").lower()


def _split_table(table: str) -> tuple[str, str]:
    schema, _, name = table.rpartition(".")
    return (schema or "public", name)


def _table_ident(table: str) -> sql.Composable:
    schema, name = _split_table(table)
    return sql.SQL(".").join([sql.Identifier(schema), sql.Identifier(name)])


class PostgresSourceAdapter:
    def __init__(self, dsn_secret: str):
        dsn = os.environ.get(dsn_secret)
        if not dsn:
            raise SystemExit(f"environment variable {dsn_secret} (source DSN) is not set")
        self._conn = psycopg.connect(dsn, autocommit=True)
        self._conn.adapters.register_loader(pg_types["uuid"].oid, _UuidTextLoader)
        with self._conn.cursor() as cur:
            cur.execute("SET default_transaction_read_only = on")
            cur.execute("SET TIME ZONE 'UTC'")
        self._types: dict[tuple[str, str], str] = {}

    def _column_type(self, table: str, column: str) -> str:
        key = (table, column)
        if key not in self._types:
            schema, name = _split_table(table)
            with self._conn.cursor() as cur:
                cur.execute(
                    "SELECT data_type FROM information_schema.columns "
                    "WHERE table_schema = %s AND table_name = %s AND column_name = %s",
                    (schema, name, column))
                row = cur.fetchone()
            if row is None:
                raise KeyError(f"column {table}.{column} not found")
            self._types[key] = row[0]
        return self._types[key]

    @staticmethod
    def _where(where: str | None) -> sql.Composable:
        return sql.SQL(" WHERE {}").format(sql.SQL(where)) if where else sql.SQL("")

    def row_count(self, table: str, where: str | None = None) -> int:
        q = sql.SQL("SELECT COUNT(*) FROM {t}{w}").format(t=_table_ident(table), w=self._where(where))
        with self._conn.cursor() as cur:
            cur.execute(q)
            return int(cur.fetchone()[0])

    def field_aggregates(self, table: str, column: str, where: str | None = None) -> dict[str, Any]:
        dtype = self._column_type(table, column)
        col = sql.Identifier(column)
        if dtype in _TEXT_TYPES:
            mm = sql.SQL("MIN({c}::text COLLATE \"C\"), MAX({c}::text COLLATE \"C\")").format(c=col)
        elif dtype in _BOOL_TYPES:
            mm = sql.SQL("MIN({c}::int)::boolean, MAX({c}::int)::boolean").format(c=col)
        else:
            mm = sql.SQL("MIN({c}), MAX({c})").format(c=col)
        q = sql.SQL("SELECT COUNT(*), COUNT({c}), COUNT(DISTINCT {c}), {mm} FROM {t}{w}").format(
            c=col, mm=mm, t=_table_ident(table), w=self._where(where))
        with self._conn.cursor() as cur:
            cur.execute(q)
            n, nn, nd, mn, mx = cur.fetchone()
            total = None
            try:
                cur.execute(sql.SQL("SELECT SUM({c}) FROM {t}{w}").format(
                    c=col, t=_table_ident(table), w=self._where(where)))
                total = cur.fetchone()[0]
            except psycopg.Error:
                total = None
        return {"count": int(n), "non_null": int(nn), "nulls": int(n) - int(nn),
                "distinct": int(nd), "min": mn, "max": mx, "sum": total}

    def fetch_keyed(self, table: str, key_cols: list[str], columns: list[str],
                    where: str | None = None, keys: list[tuple] | None = None) -> Iterable[dict[str, Any]]:
        cols = list(dict.fromkeys([*key_cols, *columns]))
        q = sql.SQL("SELECT {cols} FROM {t}").format(
            cols=sql.SQL(", ").join(sql.Identifier(c) for c in cols), t=_table_ident(table))
        clauses: list[sql.Composable] = []
        params: list[Any] = []
        if where:
            clauses.append(sql.SQL("({})").format(sql.SQL(where)))
        if keys is not None:
            if not keys:
                return
            tuples = [k if isinstance(k, tuple) else (k,) for k in keys]
            clauses.append(sql.SQL("({kc}) IN ({vals})").format(
                kc=sql.SQL(", ").join(sql.Identifier(c) for c in key_cols),
                vals=sql.SQL(", ").join(
                    sql.SQL("({})").format(sql.SQL(", ").join(sql.Placeholder() for _ in t))
                    for t in tuples)))
            for t in tuples:
                params.extend(str(v) for v in t)
        if clauses:
            q = q + sql.SQL(" WHERE ") + sql.SQL(" AND ").join(clauses)
        q = q + sql.SQL(" ORDER BY {}").format(sql.SQL(", ").join(sql.Identifier(c) for c in key_cols))
        with self._conn.transaction(), self._conn.cursor(name="recon_ext_fetch_keyed") as cur:
            cur.itersize = 2000
            cur.execute(q, params)
            for row in cur:
                yield dict(zip(cols, row))

    def key_strata(self, table: str, key_cols: list[str], n_strata: int) -> list[tuple]:
        if n_strata <= 0:
            return []
        q = sql.SQL(
            "SELECT {kc} FROM (SELECT {kc}, s, LAG(s) OVER (ORDER BY {kc}) AS prev FROM "
            "(SELECT {kc}, NTILE({n}) OVER (ORDER BY {kc}) AS s FROM {t}) a) b "
            "WHERE prev IS NULL OR prev <> s ORDER BY {kc}").format(
            kc=sql.SQL(", ").join(sql.Identifier(c) for c in key_cols),
            n=sql.Literal(int(n_strata)), t=_table_ident(table))
        with self._conn.cursor() as cur:
            cur.execute(q)
            return [tuple(r) for r in cur.fetchall()]

    def close(self) -> None:
        self._conn.close()
