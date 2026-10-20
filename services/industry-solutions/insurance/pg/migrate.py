"""Move every COMMISSION_PAY and COMMISSION_DW row from Oracle into PostgreSQL 16.

Idempotent: the target tables are truncated and reloaded in foreign-key order
with the Oracle primary keys kept, each identity sequence is moved past the
highest loaded key, and the summary materialized view is refreshed from the
migrated facts. Values travel as Decimal/datetime; nothing goes through float.
"""

from __future__ import annotations

import sys

from common import MV, TABLES, canon, oracle_columns, oracle_connect, pg_connect, query

IDENTITY_SQL = """
SELECT n.nspname, c.relname, a.attname
  FROM pg_attribute a
  JOIN pg_class c ON c.oid = a.attrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname IN ('commission_pay', 'commission_dw') AND a.attidentity <> ''
 ORDER BY 1, 2"""


def main() -> int:
    with oracle_connect() as ora, pg_connect("postgres") as pg:
        with pg.transaction():
            names = ", ".join(f"{s}.{t}" for s, t, _pk, _sums in TABLES)
            pg.execute(f"TRUNCATE {names} RESTART IDENTITY CASCADE")
            for schema, table, pk, _sums in TABLES:
                cols = oracle_columns(ora, schema, table)
                rows = query(ora, f"SELECT {', '.join(cols)} FROM {schema}.{table} ORDER BY {', '.join(pk)}")
                for row in rows:
                    for v in row:
                        canon(v)  # rejects floats before anything is written
                placeholders = ", ".join(["%s"] * len(cols))
                with pg.cursor() as cur:
                    cur.executemany(
                        f"INSERT INTO {schema}.{table} ({', '.join(cols)}) VALUES ({placeholders})", rows)
                print(f"{schema}.{table}: {len(rows)} rows")
            for schema, table, col in query(pg, IDENTITY_SQL):
                pg.execute(
                    f"SELECT setval(pg_get_serial_sequence('{schema}.{table}', '{col}'),"
                    f" COALESCE((SELECT MAX({col}) FROM {schema}.{table}), 1),"
                    f" (SELECT MAX({col}) FROM {schema}.{table}) IS NOT NULL)")
            pg.execute(f"REFRESH MATERIALIZED VIEW {MV[0]}.{MV[1]}")
            n = query(pg, f"SELECT COUNT(*) FROM {MV[0]}.{MV[1]}")[0][0]
            print(f"{MV[0]}.{MV[1]}: refreshed, {n} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
