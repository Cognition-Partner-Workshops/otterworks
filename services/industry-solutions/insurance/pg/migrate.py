"""Move every COMMISSION_PAY and COMMISSION_DW row from Oracle into PostgreSQL 16.

Idempotent: the target tables are truncated and reloaded in foreign-key order
with the Oracle primary keys kept, each identity sequence is moved past the
highest loaded key, and the summary materialized view is refreshed from the
migrated facts. Values travel as Decimal/datetime; nothing goes through float.
"""

from __future__ import annotations

import sys

from psycopg import sql

from common import MV, TABLES, canon, oracle_columns, oracle_connect, pg_connect, query

IDENTITY_SQL = """
SELECT n.nspname, c.relname, a.attname
  FROM pg_attribute a
  JOIN pg_class c ON c.oid = a.attrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname IN ('commission_pay', 'commission_dw') AND a.attidentity <> ''
 ORDER BY 1, 2"""


def main() -> int:
    with oracle_connect() as ora, pg_connect("postgres") as pg, pg.transaction():
        names = sql.SQL(", ").join(sql.Identifier(s, t) for s, t, _pk, _sums in TABLES)
        truncate = sql.Composed([sql.SQL("TRUNCATE "), names, sql.SQL(" RESTART IDENTITY CASCADE")])
        pg.execute(truncate)
        for schema, table, pk, _sums in TABLES:
            cols = oracle_columns(ora, schema, table)
            rows = query(ora, f"SELECT {', '.join(cols)} FROM {schema}.{table} ORDER BY {', '.join(pk)}")
            for row in rows:
                for v in row:
                    canon(v)  # rejects floats before anything is written
            insert = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                sql.Identifier(schema, table),
                sql.SQL(", ").join(map(sql.Identifier, cols)),
                sql.SQL(", ").join(sql.Placeholder() * len(cols)))
            with pg.cursor() as cur:
                cur.executemany(insert, rows)
            print(f"{schema}.{table}: {len(rows)} rows")
        for schema, table, col in query(pg, IDENTITY_SQL):
            top = sql.Composed([sql.SQL("(SELECT MAX("), sql.Identifier(col), sql.SQL(") FROM "),
                                sql.Identifier(schema, table), sql.SQL(")")])
            setval = sql.Composed([sql.SQL("SELECT setval(pg_get_serial_sequence(%s, %s), COALESCE("), top,
                                   sql.SQL(", 1), "), top, sql.SQL(" IS NOT NULL)")])
            pg.execute(setval, [f"{schema}.{table}", col])
        mv = sql.Identifier(*MV)
        refresh = sql.Composed([sql.SQL("REFRESH MATERIALIZED VIEW "), mv])
        count = sql.Composed([sql.SQL("SELECT COUNT(*) FROM "), mv])
        pg.execute(refresh)
        n = pg.execute(count).fetchone()[0]
        print(f"{MV[0]}.{MV[1]}: refreshed, {n} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
