"""python -m wp <command>. Run from the repository root."""
import argparse
import json
import os
import time

from . import board, iics, loader, parity, qlik, schemas
from .engines import SqlServer, connect
from .manifest import Manifest


def _run_side(eng, obj, side, m, args):
    spec = obj.get("run", {}).get(side, [])
    for step in spec:
        if isinstance(step, str):
            eng.execute(step)
        elif "iics" in step:
            path = getattr(args, f"{side}_mapping", None) or m.file(step["iics"])
            print(json.dumps(iics.run(eng, path, export_dir=args.out + "/exports")))


def cmd_parity(args, m):
    obj = m.obj(args.object)
    leg, sf = SqlServer(), connect("snowflake")
    t0 = time.time()
    if obj["type"] == "load_script":
        lres = qlik.run(leg, args.sqlserver_script or m.file(obj["legacy_script"]))
        tres = qlik.run(sf, args.snowflake_script or m.file(obj["target_script"]))
        if args.dry_run:
            print(f"dry run: statements logged to {args.dry_run}, no comparison made")
            return
        out = {}
        for block, keys in obj["compare_blocks"].items():
            out[block] = parity.compare(lres[block], tres.get(block, ([], [])), keys, obj.get("rtrim", False))
            print(block, parity.summary_line(out[block]))
            print(parity.write_evidence(f"{obj['name']}.{block}", args.label, out[block], args.out))
        green = all(r["green"] for r in out.values())
    else:
        if not args.skip_run:
            _run_side(leg, obj, "sqlserver", m, args)
            _run_side(sf, obj, "snowflake", m, args)
        lres, tres = leg.query(obj["compare"]), sf.query(obj["compare"])
        if args.dry_run:
            if not args.no_board:
                board.set_fields(sf, obj["name"], note="dry run")
            print(f"dry run: statements logged to {args.dry_run}, no comparison made")
            return
        res = parity.compare(lres, tres, obj["keys"], obj.get("rtrim", False))
        print(parity.summary_line(res))
        print(parity.write_evidence(obj["name"], args.label, res, args.out))
        green = res["green"]
        if not args.no_board:
            board.set_fields(sf, obj["name"], l1="green" if res["L1"]["pass"] else "red",
                             l2="green" if res["L2"]["pass"] else "red",
                             l3=f"{res['L3']['match_pct']}%", l4=f"{res['L4']['sampled']} diffs")
    print(f"{'GREEN' if green else 'NOT GREEN'} in {time.time() - t0:.1f}s")


def main():
    ap = argparse.ArgumentParser(prog="wp")
    ap.add_argument("--manifest")
    ap.add_argument("--dry-run", metavar="LOG", default=os.environ.get("WP_DRY_RUN"),
                    help="connect to nothing; append every statement to LOG as JSON lines")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("legacy-up", help="start SQL Server 2022 in Docker and load the frozen window")
    p = sub.add_parser("load", help="load the frozen window into one engine")
    p.add_argument("--engine", choices=["sqlserver", "snowflake"], required=True)
    p = sub.add_parser("deploy", help="run a SQL file on one engine")
    p.add_argument("--engine", choices=["sqlserver", "snowflake"], required=True)
    p.add_argument("file")
    p = sub.add_parser("sql", help="run one query on one engine and print rows")
    p.add_argument("--engine", choices=["sqlserver", "snowflake"], required=True)
    p.add_argument("query")
    p = sub.add_parser("objects", help="list manifest objects, optionally one wave")
    p.add_argument("--wave", type=int)
    p = sub.add_parser("parity", help="run both engines and compare L1 to L4")
    p.add_argument("object")
    p.add_argument("--label", default="run")
    p.add_argument("--out", default="evidence")
    p.add_argument("--skip-run", action="store_true")
    p.add_argument("--no-board", action="store_true")
    for side in ("sqlserver", "snowflake"):
        p.add_argument(f"--{side}-mapping")
        p.add_argument(f"--{side}-script")
    p = sub.add_parser("iics", help="run a mapping export on one engine")
    p.add_argument("--engine", choices=["sqlserver", "snowflake"], required=True)
    p.add_argument("mapping")
    p.add_argument("--param-file")
    p.add_argument("--export-dir", default="evidence/exports")
    p = sub.add_parser("dry-run-report", help="list the harness schemas named in a --dry-run log, per engine")
    p.add_argument("log")
    p = sub.add_parser("board", help="wave board")
    p.add_argument("action", choices=["init", "show", "set", "rollup", "serve"])
    p.add_argument("object", nargs="?")
    p.add_argument("--port", type=int, default=8765)
    for f in board.FIELDS:
        p.add_argument(f"--{f.replace('_', '-')}")
    args = ap.parse_args()
    if args.cmd == "dry-run-report":
        return dry_run_report(args.log)
    if args.dry_run:
        os.environ["WP_DRY_RUN"] = args.dry_run
    m = Manifest(args.manifest)

    if args.cmd == "legacy-up":
        loader.legacy_up()
        print(json.dumps(loader.load(_legacy(), m)))
    elif args.cmd == "load":
        eng = _legacy() if args.engine == "sqlserver" else connect("snowflake")
        print(json.dumps(loader.load(eng, m)))
    elif args.cmd == "deploy":
        eng = SqlServer() if args.engine == "sqlserver" else connect("snowflake")
        eng.run_script(open(args.file).read())
        print(f"deployed {args.file} to {args.engine}")
    elif args.cmd == "sql":
        eng = SqlServer() if args.engine == "sqlserver" else connect("snowflake")
        cols, rows = eng.query(args.query)
        print("|".join(cols))
        for r in rows:
            print("|".join("" if v is None else str(v) for v in r))
    elif args.cmd == "objects":
        for o in (m.wave(args.wave) if args.wave else m.data["objects"]):
            print(f"{o['wave']}  {o['workstream']:<11} {o['type']:<12} {o['name']}")
    elif args.cmd == "parity":
        cmd_parity(args, m)
    elif args.cmd == "iics":
        eng = SqlServer() if args.engine == "sqlserver" else connect("snowflake")
        print(json.dumps(iics.run(eng, args.mapping, args.param_file, args.export_dir)))
    elif args.cmd == "board":
        if args.action == "serve":
            return board.serve(m, args.port)
        sf = connect("snowflake")
        if args.action == "init":
            board.init(sf, m)
        elif args.action == "set":
            board.set_fields(sf, args.object, **{f: getattr(args, f) for f in board.FIELDS})
        elif args.action == "rollup":
            print(json.dumps(board.rollup(sf), indent=2, default=str))
        cols, rows = board.rows(sf)
        if args.action in ("show", "init", "set"):
            for r in rows:
                print(" | ".join("" if v is None else str(v) for v in r[:12]))


def dry_run_report(log):
    pfx = schemas.prefix()
    seen = {}
    with open(log) as fh:
        recs = [json.loads(line) for line in fh]
    for rec in recs:
        used = seen.setdefault(rec["engine"], {"statements": 0, "schemas": set(), "literal_refs": set()})
        used["statements"] += 1
        used["schemas"].update(schemas.harness_schemas_used(rec["sql"], pfx))
        used["literal_refs"].update(schemas.literal_refs(rec["sql"]))
    for eng, u in seen.items():
        print(f"{eng}: {u['statements']} statements; schemas in identifier position: "
              f"{', '.join(sorted(u['schemas'])) or '-'}; inside string literals: {', '.join(sorted(u['literal_refs'])) or '-'}")
    bad = sorted(seen.get("snowflake", {}).get("schemas", set()) & set(schemas.SCHEMAS)) if pfx else []
    if bad:
        raise SystemExit(f"unprefixed schemas sent to Snowflake: {', '.join(bad)}")


def _legacy():
    import os
    eng = SqlServer.master()
    eng.database = os.environ.get("WP_MSSQL_DATABASE", "claims_dw")
    return eng


if __name__ == "__main__":
    main()
