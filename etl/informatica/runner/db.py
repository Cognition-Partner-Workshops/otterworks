"""Relational connections to the emulated Teradata warehouse (PostgreSQL)."""

from __future__ import annotations

import sys as _run_sys
from pathlib import Path as _RunPath
_run_sys.path.insert(0, str(_RunPath(__file__).resolve().parents[3]))
from warehouse.run_config import render as _run_render


import os
import re
import zlib

import yaml
from psycopg import sql as pg_sql

from .run_scope import before_namespace

DEFAULTS = {
    "TD_HOST": "127.0.0.1",
    "TD_DB": "teradata",
    "TD_USER": "postgres",
    "TD_PASSWORD": "",
}


def default_port(ns=None):
    """Host port of the warehouse compose service for a namespace."""
    ns = ns or os.environ.get("NS") or before_namespace()
    return str(54500 + zlib.crc32(ns.encode()) % 1000)


def env(name):
    if name == "TD_PORT":
        return os.environ.get("TD_PORT") or default_port()
    return os.environ.get(name) or DEFAULTS[name]


def load_connections(path):
    if not path or not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh) or {}
    return {k.upper(): v for k, v in (doc.get("connections") or {}).items()}


def _env_sub(value):
    return re.sub(r"\$\{(\w+)\}", lambda m: env(m.group(1)) if m.group(1) in DEFAULTS or m.group(1) == "TD_PORT" else os.environ.get(m.group(1), ""), str(value))


class Connection:
    """A PowerCenter relational connection object bound to a PostgreSQL session."""

    def __init__(self, name, spec):
        self.name = name
        self.spec = spec or {}
        self.default_database = self.spec.get("default_database", "")
        self._conn = None
        self._tables: dict = {}

    def dsn(self):
        s = self.spec
        return {
            "host": _env_sub(s.get("host", "${TD_HOST}")),
            "port": _env_sub(s.get("port", "${TD_PORT}")),
            "dbname": _env_sub(s.get("database", "${TD_DB}")),
            "user": _env_sub(s.get("user", "${TD_USER}")),
            "password": _env_sub(s.get("password", "${TD_PASSWORD}")),
        }

    @property
    def conn(self):
        if self._conn is None:
            import psycopg

            self._conn = psycopg.connect(**self.dsn(), autocommit=False)
        return self._conn

    def close(self, commit=True):
        if self._conn is not None:
            if commit:
                self._conn.commit()
            else:
                self._conn.rollback()
            self._conn.close()
            self._conn = None

    # -- identifier resolution ---------------------------------------------

    def resolve_table(self, owner, table):
        """Find the physical (schema, table, {COLUMN: column}) case-insensitively."""
        owner = owner or self.default_database
        key = ((owner or "").upper(), table.upper())
        if key in self._tables:
            return self._tables[key]
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT table_schema, table_name FROM information_schema.tables "
                "WHERE upper(table_name) = %s AND (%s = '' OR upper(table_schema) = %s) ORDER BY table_schema",
                (key[1], key[0], key[0]),
            )
            row = cur.fetchone()
            if row is None:
                raise LookupError(f"table {owner}.{table} not found on connection {self.name}")
            schema, name = row
            cur.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_schema = %s AND table_name = %s",
                (schema, name),
            )
            cols = {r[0].upper(): r[0] for r in cur.fetchall()}
        self._tables[key] = (schema, name, cols)
        return self._tables[key]


def qi(name):
    return identifier(name).as_string()


def identifier(*parts):
    if not parts or any(not isinstance(p, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9$]*', p) for p in parts):
        raise ValueError(f'Invalid identifier: {parts!r}')
    return pg_sql.Identifier(*parts)


def compose(template, *parts):
    if any(not isinstance(p, pg_sql.Composable) for p in parts):
        raise TypeError('Expected validated SQL components')
    return pg_sql.SQL(template).format(*parts).as_string()


def bind_sql(template, expand):
    """Bind PowerCenter parameter values without letting expansion alter SQL syntax."""
    if '\x00' in template:
        raise ValueError('Invalid SQL template')
    token = re.compile(r"'(?:[^']|'')*'|\$\$?[A-Za-z_][A-Za-z_0-9]*")
    values = []

    def replace(match):
        text = match.group()
        if text.startswith("'"):
            if not re.search(r'\$\$?[A-Za-z_]', text):
                return text
            value = expand(text[1:-1].replace("''", "'"))
        else:
            value = expand(text)
            if re.fullmatch(r'[+-]?\d+', value):
                value = int(value)
        values.append(value)
        return '\x00'

    query = token.sub(replace, template)
    return (query.replace('%', '%%').replace('\x00', '%s'), tuple(values)) if values else (template, ())


def qualified(schema, table):
    return f"{qi(schema)}.{qi(table)}"


def rewrite_sql(sql, conn: Connection):
    """Map OWNER.TABLE references in override SQL onto physical names."""

    def repl(m):
        owner, table = m.group(1), m.group(2)
        try:
            schema, name, _ = conn.resolve_table(owner, table)
        except LookupError:
            return m.group(0)
        return qualified(schema, name)

    return re.sub(r"\b(SFX_[A-Z]+)\.([A-Z_][A-Z0-9_]*)\b", repl, sql, flags=re.IGNORECASE)
