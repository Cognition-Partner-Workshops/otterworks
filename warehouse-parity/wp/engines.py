"""Connections to the two engines. Everything else talks to these two classes."""
import json
import os
import re
import sys

from . import schemas

IDENT = re.compile(r'^"?[A-Za-z_][A-Za-z0-9_$]*"?(\."?[A-Za-z_][A-Za-z0-9_$]*"?)*$')


def ident(name):
    """Reject anything that is not a plain or quoted, optionally dotted, identifier."""
    if not IDENT.match(name):
        raise ValueError(f"not a SQL identifier: {name!r}")
    return name


def stmt(template, **names):
    """Fill identifier slots in a statement; values still go through bind parameters."""
    return template.format(**{k: ident(v) for k, v in names.items()})


def insert_sql(table, cols, nrows, ph="%s"):
    row = "(" + ",".join([ph] * len(cols)) + ")"
    return (stmt("INSERT INTO {t} ", t=table) + "(" + ",".join(ident(c) for c in cols) + ") VALUES "
            + ",".join([row] * nrows))


def update_sql(table, cols, where):
    sets = ", ".join(ident(c) + " = %s" for c in cols)
    return stmt("UPDATE {t} SET ", t=table) + sets + " " + where


def _mssql_connect(database, args):
    if dry_run_log():
        return DryRunConnection("sqlserver", dry_run_log())
    import pymssql
    return pymssql.connect(database=database, **args)


def legacy_password():
    return os.environ.get("WP_MSSQL_PASSWORD", "Parity#Local1")

GO = re.compile(r"^\s*GO\s*;?\s*$", re.I | re.M)
SYNAPSE_WITH = re.compile(
    r"\)\s*WITH\s*\(\s*(DISTRIBUTION|CLUSTERED|HEAP)[^;]*?\)\s*(;|\n\s*GO|$)", re.I | re.S)


def strip_synapse_options(sql):
    """Dedicated pool table options mean nothing to SQL Server 2022; drop them."""
    return SYNAPSE_WITH.sub(lambda m: ")" + m.group(2), sql)


class DryRunConnection:
    """Stands in for a DB-API connection under WP_DRY_RUN: logs each statement, runs nothing."""

    def __init__(self, engine, log):
        self.engine, self.log = engine, log

    def record(self, sql, params=None):
        with open(self.log, "a") as fh:
            fh.write(json.dumps({"engine": self.engine, "sql": sql, "params": params is not None}) + "\n")

    def cursor(self):
        return _DryRunCursor(self)

    def execute_string(self, sql, remove_comments=False):
        self.record(sql)
        return []


class _DryRunCursor:
    description, rowcount = [], 1

    def __init__(self, conn):
        self.conn = conn

    def execute(self, sql, params=None):
        self.conn.record(sql, params)

    def executemany(self, sql, seq):
        self.conn.record(sql, seq)

    def fetchall(self):
        return []

    def nextset(self):
        return None


def dry_run_log():
    return os.environ.get("WP_DRY_RUN") or None


class SqlServer:
    name = "sqlserver"

    def resolve(self, table):
        return table

    def __init__(self, database=None):
        self.database = database or os.environ.get("WP_MSSQL_DATABASE", "claims_dw")
        self._args = dict(
            server=os.environ.get("WP_MSSQL_HOST", "localhost"),
            port=int(os.environ.get("WP_MSSQL_PORT", "1433")),
            user=os.environ.get("WP_MSSQL_USER", "sa"),
            password=legacy_password(),
            autocommit=True,
        )
        self.conn = _mssql_connect(self.database, self._args)

    @classmethod
    def master(cls):
        obj = cls.__new__(cls)
        obj.database = "master"
        obj._args = dict(server=os.environ.get("WP_MSSQL_HOST", "localhost"),
                         port=int(os.environ.get("WP_MSSQL_PORT", "1433")),
                         user=os.environ.get("WP_MSSQL_USER", "sa"),
                         password=legacy_password(),
                         autocommit=True)
        obj.conn = _mssql_connect("master", obj._args)
        return obj

    def execute(self, sql, params=None):
        cur = self.conn.cursor()
        cur.execute(sql, params) if params else cur.execute(sql)
        while cur.nextset():
            pass
        return cur.rowcount

    def run_script(self, sql):
        for batch in GO.split(strip_synapse_options(sql)):
            if batch.strip():
                self.execute(batch)

    def query(self, sql):
        cur = self.conn.cursor()
        cur.execute(sql)
        cols = [d[0].lower() for d in cur.description]
        return cols, [tuple(r) for r in cur.fetchall()]

    def insert_rows(self, table, cols, rows, batch=150):
        cur = self.conn.cursor()
        for i in range(0, len(rows), batch):
            chunk = rows[i:i + batch]
            cur.execute(insert_sql(table, cols, len(chunk)), tuple(v for r in chunk for v in r))

    def nullability(self, table):
        schema, name = table.split(".")
        _, rows = self.query(
            "SELECT column_name, is_nullable FROM information_schema.columns "
            f"WHERE table_schema = '{schema}' AND table_name = '{name}' ORDER BY ordinal_position")
        return {c.lower(): n == "YES" for c, n in rows}


class Snowflake:
    name = "snowflake"

    def __init__(self):
        self.prefix = schemas.prefix()
        self.default_schema = schemas.schema_name("DW", self.prefix)
        if dry_run_log():
            self.conn = DryRunConnection(self.name, dry_run_log())
            return
        import snowflake.connector
        from cryptography.hazmat.primitives import serialization
        pem = os.environ["WP_SF_PRIVATE_KEY"].replace("\\n", "\n").encode()
        key = serialization.load_pem_private_key(pem, password=None).private_bytes(
            serialization.Encoding.DER, serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption())
        self.conn = snowflake.connector.connect(
            account=os.environ["WP_SF_ACCOUNT"], user=os.environ["WP_SF_USER"],
            private_key=key, role=os.environ.get("WP_SF_ROLE"),
            warehouse=os.environ.get("WP_SF_WAREHOUSE"),
            database=os.environ.get("WP_SF_DATABASE"), schema=self.default_schema,
            session_parameters={"QUERY_TAG": "warehouse-parity"})

    def sql(self, text):
        """Every statement bound for Snowflake goes through here (schema prefix remap)."""
        if not self.prefix:
            return text
        leaks = schemas.literal_refs(text)
        if leaks:
            print(f"warning: string literal names unprefixed schema {', '.join(leaks)} "
                  "(dynamic SQL is not remapped)", file=sys.stderr)
        return schemas.remap(text, self.prefix)

    def execute(self, sql, params=None):
        cur = self.conn.cursor()
        cur.execute(self.sql(sql), params)
        return cur.rowcount

    def run_script(self, sql):
        for cur in self.conn.execute_string(self.sql(sql), remove_comments=False):
            pass

    def query(self, sql):
        cur = self.conn.cursor()
        cur.execute(self.sql(sql))
        cols = [d[0].lower() for d in cur.description]
        return cols, [tuple(r) for r in cur.fetchall()]

    def insert_rows(self, table, cols, rows, batch=5000):
        cur = self.conn.cursor()
        sql = self.sql(insert_sql(table, cols, 1))
        for i in range(0, len(rows), batch):
            cur.executemany(sql, rows[i:i + batch])

    def resolve(self, table):
        """Loader helper: find the stored name even when the DDL quoted a mixed-case identifier."""
        schema, name = table.split(".")
        schema = schemas.schema_name(schema, self.prefix)
        _, rows = self.query("SELECT table_name FROM information_schema.tables "
                             f"WHERE table_schema = UPPER('{schema}') AND UPPER(table_name) = UPPER('{name}')")
        return f'{schema}."{rows[0][0]}"' if rows else table

    def nullability(self, table):
        schema, name = table.split(".")
        schema = schemas.schema_name(schema, self.prefix)
        _, rows = self.query(
            "SELECT column_name, is_nullable FROM information_schema.columns "
            f"WHERE table_schema = UPPER('{schema}') AND UPPER(table_name) = UPPER('{name}') "
            "ORDER BY ordinal_position")
        return {c.lower(): n == "YES" for c, n in rows}


def connect(name):
    return {"sqlserver": SqlServer, "snowflake": Snowflake}[name]()
