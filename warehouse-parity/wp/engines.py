"""Connections to the two engines. Everything else talks to these two classes."""
import os
import re

GO = re.compile(r"^\s*GO\s*;?\s*$", re.I | re.M)
SYNAPSE_WITH = re.compile(
    r"\)\s*WITH\s*\(\s*(DISTRIBUTION|CLUSTERED|HEAP)[^;]*?\)\s*(;|\n\s*GO|$)", re.I | re.S)


def strip_synapse_options(sql):
    """Dedicated pool table options mean nothing to SQL Server 2022; drop them."""
    return SYNAPSE_WITH.sub(lambda m: ")" + m.group(2), sql)


class SqlServer:
    name = "sqlserver"

    def resolve(self, table):
        return table

    def __init__(self, database=None):
        import pymssql
        self.database = database or os.environ.get("WP_MSSQL_DATABASE", "claims_dw")
        self._args = dict(
            server=os.environ.get("WP_MSSQL_HOST", "localhost"),
            port=int(os.environ.get("WP_MSSQL_PORT", "1433")),
            user=os.environ.get("WP_MSSQL_USER", "sa"),
            password=os.environ.get("WP_MSSQL_PASSWORD", "Parity#Local1"),
            autocommit=True,
        )
        self.conn = pymssql.connect(database=self.database, **self._args)

    @classmethod
    def master(cls):
        import pymssql
        obj = cls.__new__(cls)
        obj.database = "master"
        obj._args = dict(server=os.environ.get("WP_MSSQL_HOST", "localhost"),
                         port=int(os.environ.get("WP_MSSQL_PORT", "1433")),
                         user=os.environ.get("WP_MSSQL_USER", "sa"),
                         password=os.environ.get("WP_MSSQL_PASSWORD", "Parity#Local1"),
                         autocommit=True)
        obj.conn = pymssql.connect(database="master", **obj._args)
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
        ph = "(" + ",".join(["%s"] * len(cols)) + ")"
        head = f"INSERT INTO {table} ({','.join(cols)}) VALUES "
        cur = self.conn.cursor()
        for i in range(0, len(rows), batch):
            chunk = rows[i:i + batch]
            cur.execute(head + ",".join([ph] * len(chunk)), tuple(v for r in chunk for v in r))

    def nullability(self, table):
        schema, name = table.split(".")
        _, rows = self.query(
            "SELECT column_name, is_nullable FROM information_schema.columns "
            f"WHERE table_schema = '{schema}' AND table_name = '{name}' ORDER BY ordinal_position")
        return {c.lower(): n == "YES" for c, n in rows}


class Snowflake:
    name = "snowflake"

    def __init__(self):
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
            database=os.environ.get("WP_SF_DATABASE"), schema="DW",
            session_parameters={"QUERY_TAG": "warehouse-parity"})

    def execute(self, sql, params=None):
        cur = self.conn.cursor()
        cur.execute(sql, params)
        return cur.rowcount

    def run_script(self, sql):
        for cur in self.conn.execute_string(sql, remove_comments=False):
            pass

    def query(self, sql):
        cur = self.conn.cursor()
        cur.execute(sql)
        cols = [d[0].lower() for d in cur.description]
        return cols, [tuple(r) for r in cur.fetchall()]

    def insert_rows(self, table, cols, rows, batch=5000):
        cur = self.conn.cursor()
        sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join(['%s'] * len(cols))})"
        for i in range(0, len(rows), batch):
            cur.executemany(sql, rows[i:i + batch])

    def resolve(self, table):
        """Loader helper: find the stored name even when the DDL quoted a mixed-case identifier."""
        schema, name = table.split(".")
        _, rows = self.query("SELECT table_name FROM information_schema.tables "
                             f"WHERE table_schema = UPPER('{schema}') AND UPPER(table_name) = UPPER('{name}')")
        return f'{schema}."{rows[0][0]}"' if rows else table

    def nullability(self, table):
        schema, name = table.split(".")
        _, rows = self.query(
            "SELECT column_name, is_nullable FROM information_schema.columns "
            f"WHERE table_schema = UPPER('{schema}') AND UPPER(table_name) = UPPER('{name}') "
            "ORDER BY ordinal_position")
        return {c.lower(): n == "YES" for c, n in rows}


def connect(name):
    return {"sqlserver": SqlServer, "snowflake": Snowflake}[name]()
