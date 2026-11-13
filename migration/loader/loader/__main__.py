import argparse
import json
import os
from pathlib import Path

import oracledb

from .common import token_name
from .frozen import extract, load_duckdb


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    source = sub.add_parser("extract")
    source.add_argument("--tables", nargs="+", required=True)
    source.add_argument("--out", required=True)
    source.add_argument("--ttl-hours", type=int, default=24)
    target = sub.add_parser("load")
    target.add_argument("--manifest", required=True)
    target.add_argument("--out", default=".")
    target.add_argument("--target", choices=["duckdb", "snowflake"], required=True)
    cleanup = sub.add_parser("teardown")
    cleanup.add_argument("--target", choices=["duckdb", "snowflake"], default="snowflake")
    cleanup.add_argument("--out", default=".")
    for command in (source, target, cleanup):
        command.add_argument("--token", required=True)
        command.add_argument("--prefix", default="MIGRATION")
    args = parser.parse_args()
    base = token_name(args.token, args.prefix)
    if args.command == "extract":
        oracledb.defaults.fetch_decimals = True
        with oracledb.connect(user=os.environ["ORACLE_USER"], password=os.environ["ORACLE_PASSWORD"],
                              dsn=os.environ["ORACLE_DSN"]) as conn:
            manifest = extract(conn, args.tables, args.out, args.token, args.ttl_hours)
        print(f"Frozen tables: {len(manifest['objects'])}")
    elif args.command == "load":
        if args.target == "duckdb":
            print(load_duckdb(args.manifest, args.out, args.token, args.prefix))
        else:
            from .snowflake import connect, load

            with connect() as conn:
                print(load(conn, args.manifest, args.token, args.prefix))
    elif args.target == "duckdb":
        path = Path(args.out) / f"{base}.duckdb"
        path.unlink(missing_ok=True)
        remaining = list(Path(args.out).glob(f"*_{args.token.upper()}_AFTER*"))
        print(json.dumps({"remaining": [str(p) for p in remaining]}))
        return int(bool(remaining))
    else:
        from .snowflake import connect, teardown

        with connect() as conn:
            report = teardown(conn, args.token, args.prefix)
        print(json.dumps(report))
        return int(bool(report["remaining"] or report["errors"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
