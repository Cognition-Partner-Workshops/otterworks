"""Load the Spark fixture into isolated schemas without changing RAW or COMPAT."""
import argparse
import csv
import hashlib
from pathlib import Path
import sys
import uuid

from sfx_conn import connect

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "etl/spark/jobs/py"))
from common.schemas import SCHEMAS, TABLES


def snowflake_type(kind):
    return {"TEXT": "VARCHAR", "TIMESTAMP": "TIMESTAMP_NTZ", "BIGINT": "BIGINT",
            "DATE": "DATE"}.get(kind, kind.replace("DECIMAL", "NUMBER"))


def inspect_files(landing, area, table):
    files = sorted((Path(landing) / area / table).glob("*.psv"))
    if not files:
        raise FileNotFoundError(f"No landing files: {area}/{table}")
    count = 0
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.name.encode())
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        with path.open(newline="") as stream:
            reader = csv.reader(stream, delimiter="|")
            if next(reader, None) != [name for name, _ in SCHEMAS[table]]:
                raise ValueError(f"Header mismatch: {path}")
            count += sum(1 for _ in reader)
    return files, count, digest.hexdigest()


def load(landing, tables=None):
    available = {f"{area}.{table}": (area, table)
                 for area, names in TABLES.items() for table in names}
    if tables is not None and (not isinstance(tables, list) or not tables or
                               any(not isinstance(name, str) or name not in available for name in tables)):
        raise ValueError("Invalid ingest tables")
    selected = available if tables is None else dict.fromkeys(tables)
    manifest = [(area, table, *inspect_files(landing, area, table))
                for area, table in (available[name] for name in selected)]
    rows = []
    with connect("load", "spark-landing", job="_landing") as conn:
        with conn.cursor() as cur:
            for area, table, files, expected, digest in manifest:
                schema = f"SPARK_RAW_{area.upper()}"
                target = f"{schema}.{table}"
                stage_table = f"{schema}._SFX_STAGE_{uuid.uuid4().hex.upper()}"
                columns = ", ".join(f'"{name}" {snowflake_type(kind)}' for name, kind in SCHEMAS[table])
                # Schemas are provisioned by V010; the loader has no database CREATE SCHEMA.
                # DDL identifiers/types come from the repository schema map; stage adds a UUID.
                # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                cur.execute(f"CREATE TABLE IF NOT EXISTS {target} ({columns}) COMMENT='sfx-d1110 spark landing'")
                # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                cur.execute(f"DESC TABLE {target}")
                if [row[0] for row in cur.fetchall()] != [name for name, _ in SCHEMAS[table]]:
                    raise ValueError(f"Existing Spark table schema differs: {target}")
                prefix = f"LANDING.LANDING_STAGE/spark/{area}/{table}/{digest}"
                try:
                    # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                    cur.execute(f"CREATE TEMP TABLE {stage_table} ({columns})")
                    for path in files:
                        uri = path.resolve().as_uri().replace("'", "''")
                        # URI is file:// with escaped quotes; stage prefix uses manifest names and SHA256.
                        # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                        cur.execute(f"PUT '{uri}' @{prefix}/ AUTO_COMPRESS=FALSE OVERWRITE=FALSE")
                    cur.execute(f"COPY INTO {stage_table} FROM @{prefix}/ "
                                "FILE_FORMAT=(FORMAT_NAME='LANDING.PSV_SKIP' ESCAPE_UNENCLOSED_FIELD=NONE NULL_IF=('')) "
                                "ON_ERROR=ABORT_STATEMENT FORCE=TRUE")
                    # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                    cur.execute(f"SELECT COUNT(*) FROM {stage_table}")
                    actual = cur.fetchone()[0]
                    if actual != expected:
                        raise ValueError(f"Row count mismatch: {target}: {actual} != {expected}")
                    # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                    cur.execute(f"INSERT OVERWRITE INTO {target} SELECT * FROM {stage_table}")
                    # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                    cur.execute(f"SELECT COUNT(*) FROM {target}")
                    actual = cur.fetchone()[0]
                    if actual != expected:
                        raise ValueError(f"Final count mismatch: {target}")
                    rows.append((target, expected, actual))
                    print(f"| {target} | {expected} | {actual} |", flush=True)
                finally:
                    # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                    cur.execute(f"DROP TABLE IF EXISTS {stage_table}")
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--landing-dir", type=Path, default=REPO / "etl/spark/.data/landing")
    parser.add_argument("--tables", help="Comma-separated area.TABLE names to refresh (default: all)")
    args = parser.parse_args()
    print("| Table | Local PSV records | Snowflake rows |\n|---|---:|---:|")
    load(args.landing_dir, args.tables.split(",") if args.tables is not None else None)
