"""Load the Spark fixture into isolated schemas without changing RAW or COMPAT."""

import sys as _run_sys
from pathlib import Path as _RunPath
_run_sys.path.insert(0, str(_RunPath(__file__).resolve().parents[2]))
from warehouse.run_config import render as _run_render
from warehouse.sql import compose, identifier, stage
from psycopg import sql

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
            for block in iter(lambda: _run_render(stream.read(1024 * 1024)), b""):
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
                columns = sql.SQL(', ').join(sql.Composed([identifier(name), sql.SQL(' ' + snowflake_type(kind))])
                                             for name, kind in SCHEMAS[table])
                # Schemas are provisioned by V010; the loader has no database CREATE SCHEMA.
                cur.execute(compose('CREATE TABLE IF NOT EXISTS {} ({}) COMMENT=%s', identifier(target), columns),
                            (_run_render('__RUN_TOKEN__ spark landing'),))
                cur.execute(compose('DESC TABLE {}', identifier(target)))
                if [row[0] for row in cur.fetchall()] != [name for name, _ in SCHEMAS[table]]:
                    raise ValueError(f"Existing Spark table schema differs: {target}")
                prefix = f"LANDING.LANDING_STAGE/spark/{area}/{table}/{digest}"
                try:
                    cur.execute(compose('CREATE TEMP TABLE {} ({})', identifier(stage_table), columns))
                    for path in files:
                        uri = path.resolve().as_uri()
                        cur.execute(compose('PUT %s {} AUTO_COMPRESS=FALSE OVERWRITE=FALSE', stage(prefix + '/')), (uri,))
                    cur.execute(compose("COPY INTO {} FROM {} "
                                "FILE_FORMAT=(FORMAT_NAME='LANDING.PSV_SKIP' ESCAPE_UNENCLOSED_FIELD=NONE NULL_IF=('')) "
                                "ON_ERROR=ABORT_STATEMENT FORCE=TRUE", identifier(stage_table), stage(prefix + '/')))
                    cur.execute(compose('SELECT COUNT(*) FROM {}', identifier(stage_table)))
                    actual = cur.fetchone()[0]
                    if actual != expected:
                        raise ValueError(f"Row count mismatch: {target}: {actual} != {expected}")
                    cur.execute(compose('INSERT OVERWRITE INTO {} SELECT * FROM {}', identifier(target), identifier(stage_table)))
                    cur.execute(compose('SELECT COUNT(*) FROM {}', identifier(target)))
                    actual = cur.fetchone()[0]
                    if actual != expected:
                        raise ValueError(f"Final count mismatch: {target}")
                    rows.append((target, expected, actual))
                    print(f"| {target} | {expected} | {actual} |", flush=True)
                finally:
                    cur.execute(compose('DROP TABLE IF EXISTS {}', identifier(stage_table)))
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--landing-dir", type=Path, default=REPO / "etl/spark/.data/landing")
    parser.add_argument("--tables", help="Comma-separated area.TABLE names to refresh (default: all)")
    args = parser.parse_args()
    print("| Table | Local PSV records | Snowflake rows |\n|---|---:|---:|")
    load(args.landing_dir, args.tables.split(",") if args.tables is not None else None)
