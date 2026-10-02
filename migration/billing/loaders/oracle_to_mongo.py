#!/usr/bin/env python3
"""Oracle -> MongoDB loader for the OtterWorks billing migration (wave loads and delta loads).

Reads the source tables of the requested collections with python-oracledb (every session
`SET TRANSACTION READ ONLY`, SELECT only, principal checked for write-capable privileges),
maps the rows with recon.py's reference mapping (`load_documents`: primary rows through
`map_source_row`, embedded child tables grouped under their parent, orphans partitioned into
the quarantine collection; so loader documents are by construction what the recon expects),
and bulk-upserts on `_id` (ReplaceOne, upsert=True) into the migration database only. Upsert
on `_id` makes a rerun a no-op (0 upserted, 0 modified), which is the idempotency proof; the
same command is the delta load of the parallel run. The secondary indexes declared in
mapping_spec.json are created idempotently; an index whose build is deferred is not created.

    uv run --no-project --with oracledb==2.5.1 --with pymongo==4.10.1 \
      python3 migration/billing/loaders/oracle_to_mongo.py --mode live \
        --collections codes,tenants,plans,subscriptions,subscriptions_hist --passes 2 \
        --report migration/billing/recon/out/U1.load.json
    uv run --no-project --with oracledb==2.5.1 --with pymongo==4.10.1 \
      python3 migration/billing/loaders/oracle_to_mongo.py --mode live \
        --collections usage_events,rating_periods --passes 2 \
        --report migration/billing/recon/out/U3.load.json
    ... --collections credit_notes,invoice_feed,invoice_feed_quarantine,invoices --passes 2 \
        --report migration/billing/recon/out/U4.load.json

A collection with embedded children is loaded from its primary table plus every child table;
a quarantine collection is loaded together with the collection it quarantines (the orphan set
is defined by the parent keys of that same read), so both names must be in --collections.

    # U2: customers embeds ENTITY_ATTR_VALUE as attributes[] (one embedded child table, no quarantine)
    uv run --no-project --with oracledb==2.5.1 --with pymongo==4.10.1 \
      python3 migration/billing/loaders/oracle_to_mongo.py --mode live \
        --collections customers,customers_hist --passes 2 \
        --report migration/billing/recon/out/U2.load.json

Secrets by name only: `OW_TP_ORACLE_RO_DSN` (user/password@dsn or JSON) and `MONGODB_ATLAS_URI`.
`--mode fixture` loads the local Oracle Free fixture into a loopback mongod and refuses
anything that is not loopback; `--mode live` refuses loopback on either side.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BILLING = HERE.parent
sys.path.insert(0, str(BILLING / "recon"))

import recon  # noqa: E402

U1_COLLECTIONS = ["codes", "tenants", "plans", "subscriptions", "subscriptions_hist"]
U4_COLLECTIONS = ["credit_notes", "invoice_feed", "invoice_feed_quarantine", "invoices"]


def _loopback(hosts) -> bool:
    return all(h in recon.LOCAL_HOSTS for h in hosts)


def _target(uri: str, database: str, secret_name: str):
    from pymongo import MongoClient

    client = MongoClient(uri, tz_aware=True, serverSelectionTimeoutMS=15000, appname="ow-billing-loader")
    client.admin.command("ping")
    hosts = sorted({h for h, _port in client.nodes})
    return client, client[database], hosts


def _collection_maps(inputs: recon.Inputs, names: list[str]) -> list[recon.CollectionMap]:
    by_name = {c.name: c for c in inputs.collections}
    missing = [n for n in names if n not in by_name]
    if missing:
        raise SystemExit(f"not in mapping_spec.json#collections: {missing}")
    quarantined_by = {e.quarantine_collection: c.name
                      for c in inputs.collections for e in c.embedded if e.quarantine_collection}
    for n in names:
        cm = by_name[n]
        if cm.quarantine_of is not None and quarantined_by.get(n) not in names:
            raise SystemExit(f"{n} quarantines the orphans of {quarantined_by.get(n)}; load both in the same run")
        for e in cm.embedded:
            if e.quarantine_collection and e.quarantine_collection not in names:
                raise SystemExit(f"{n}.{e.path} sends orphans to {e.quarantine_collection}; load both in the same run")
    return [by_name[n] for n in names]


def read_tables(source, maps: list[recon.CollectionMap]) -> dict[str, list[dict]]:
    """One read per source table: the primary table of every requested collection plus the
    child tables it embeds (a quarantine collection reads nothing; its rows are the orphans)."""
    tables: dict[str, list[dict]] = {}
    for cm in maps:
        if cm.quarantine_of is not None:
            continue
        for table in [cm.table, *(e.table for e in cm.embedded)]:
            if table not in tables:
                tables[table] = source.rows(table)
    return tables


def map_documents(inputs: recon.Inputs, maps: list[recon.CollectionMap], tables: dict[str, list[dict]],
                  now: dt.datetime) -> dict[str, list[dict]]:
    """recon.load_documents over the tables read for this run, restricted to the requested names."""
    docs = recon.load_documents(inputs, tables, now)
    return {cm.name: docs.get(cm.name, []) for cm in maps}


def load_collection(db, cm: recon.CollectionMap, docs: list[dict], tables: dict[str, list[dict]]) -> dict:
    from pymongo import ReplaceOne

    stats = {"table": cm.table, "documents": len(docs), "upserted": 0, "matched": 0, "modified": 0}
    if cm.quarantine_of is not None:
        stats["source_rows"] = len(docs)
        stats["quarantine_of"] = cm.quarantine_of.table
    else:
        stats["source_rows"] = len(tables.get(cm.table, []))
        if cm.embedded:
            stats["embedded"] = {
                e.path: {"table": e.table, "source_rows": len(tables.get(e.table, [])),
                         "embedded_rows": sum(len(d.get(e.path, [])) if e.shape != "subdoc" else int(e.path in d)
                                              for d in docs)}
                for e in cm.embedded}
    if docs:
        ops = [ReplaceOne({"_id": d["_id"]}, d, upsert=True) for d in docs]
        res = db[cm.name].bulk_write(ops, ordered=False)
        stats.update(upserted=res.upserted_count, matched=res.matched_count, modified=res.modified_count)
    stats["target_count_after"] = db[cm.name].count_documents({})
    return stats


def ensure_indexes(spec: dict, db, names: list[str]) -> list[dict]:
    created = []
    for c in spec["collections"]:
        if c["name"] not in names:
            continue
        for ix in c.get("indexes", []):
            options = dict(ix.get("options", {}))
            if ix.get("deferred") or options.pop("build", None) == "deferred":
                continue
            keys = [(k, v) for k, v in ix["keys"].items()]
            db[c["name"]].create_index(keys, name=ix["name"], **options)
            created.append({"collection": c["name"], "name": ix["name"], "keys": ix["keys"], "options": options})
    return created


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--mode", choices=["live", "fixture"], required=True)
    p.add_argument("--collections", default=",".join(U1_COLLECTIONS),
                   help="comma-separated collection names from mapping_spec.json (default: U1; "
                        f"U4 is {','.join(U4_COLLECTIONS)})")
    p.add_argument("--spec", default=str(recon.SPEC_PATH))
    p.add_argument("--tolerances", default=str(recon.TOLERANCES_PATH))
    p.add_argument("--oracle-dsn-env", default=None, help="env var holding the Oracle DSN (default: tolerances.json#source.dsn_secret)")
    p.add_argument("--mongo-uri-env", default=None, help="env var holding the Mongo URI (default: tolerances.json#target.uri_secret)")
    p.add_argument("--mongo-db", default=None, help="target database (default: mapping_spec.json#target.database)")
    p.add_argument("--passes", type=int, default=1, help="load N times; pass 2+ must be a no-op")
    p.add_argument("--no-indexes", action="store_true")
    p.add_argument("--report", default=None, help="write a JSON load report here")
    args = p.parse_args(argv)

    inputs = recon.build_inputs(Path(args.spec), Path(args.tolerances), None)
    tol = inputs.tolerances
    dsn_env = args.oracle_dsn_env or tol.get("source", {}).get("dsn_secret", "OW_TP_ORACLE_RO_DSN")
    uri_env = args.mongo_uri_env or tol.get("target", {}).get("uri_secret", "MONGODB_ATLAS_URI")
    schema = tol.get("source", {}).get("schema", "OW_BILLING")
    database = args.mongo_db or inputs.spec["target"]["database"]
    names = [n.strip() for n in args.collections.split(",") if n.strip()]
    maps = _collection_maps(inputs, names)
    if args.passes < 1:
        raise SystemExit("--passes must be >= 1")

    source = recon.OracleSource(recon._require_env(dsn_env), dsn_env, schema, 1)
    client, db, hosts = _target(recon._require_env(uri_env), database, uri_env)
    if args.mode == "live":
        if database != inputs.spec["target"]["database"]:
            raise SystemExit(f"--mode live writes only {inputs.spec['target']['database']}")
        if source.dsn_host in recon.LOCAL_HOSTS or _loopback(hosts):
            raise SystemExit("--mode live refuses loopback source/target; use --mode fixture")
    else:
        if not _loopback(hosts):
            raise SystemExit("--mode fixture only loads into a loopback mongod; it never touches Atlas")

    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    report = {
        "kind": "load-report", "run_mode": args.mode, "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": source.describe(),
        "target": {"system": "mongodb", "database": database, "uri_secret": uri_env, "hosts": hosts,
                   "statements": "bulk_write ReplaceOne(upsert=True) on _id; create_index"},
        "inputs": {"mapping_spec": {"path": "migration/billing/mapping_spec.json", "sha256": inputs.spec_sha},
                   "tolerances": {"path": "migration/billing/tolerances.json", "sha256": inputs.tolerances_sha}},
        "collections": names, "passes": [], "indexes": [],
    }
    try:
        for n in range(1, args.passes + 1):
            t0 = time.monotonic()
            tables = read_tables(source, maps)
            docs = map_documents(inputs, maps, tables, now)
            stats = {cm.name: load_collection(db, cm, docs[cm.name], tables) for cm in maps}
            noop = all(s["upserted"] == 0 and s["modified"] == 0 for s in stats.values())
            report["passes"].append({"pass": n, "seconds": round(time.monotonic() - t0, 3), "noop": noop, "collections": stats})
            total = sum(s["documents"] for s in stats.values())
            print(f"pass {n}: {total} documents -> {database} "
                  + ", ".join(f"{k}: +{v['upserted']} ~{v['modified']} ={v['target_count_after']}" for k, v in stats.items())
                  + ("  (no-op)" if noop else ""))
        if not args.no_indexes:
            report["indexes"] = ensure_indexes(inputs.spec, db, names)
            print(f"indexes: {len(report['indexes'])} ensured on {database}")
    finally:
        client.close()
    report["rerun_noop"] = (len(report["passes"]) >= 2 and all(p["noop"] for p in report["passes"][1:])) if args.passes > 1 else None
    if args.report:
        out = Path(args.report)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, sort_keys=False) + "\n")
        print(f"report -> {out}")
    if args.passes > 1 and not report["rerun_noop"]:
        print("rerun was NOT a no-op", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
