#!/usr/bin/env python3
"""Wave 1 readiness (s4.1.0-preflight): run recon.py in fixture mode over U1's collections only.

Drives migration/billing/recon/recon.py the way its self-test does (a faithful synthetic copy of
migration/billing/fixtures/demo.json loaded through the mapping into a loopback mongod or memory),
restricted to the collections units.json names for the unit. Output is a recon report with
run_mode=fixture and merge_evidence=false; the live report UNT-15 owes replaces it, never this.

    uv run --no-project --with pymongo==4.10.1 --with jsonschema==4.25.1 --with rfc3339-validator==0.1.4 \
      python3 migration/billing/waves/wave1/fixture_recon.py --unit U1 [--mongo-uri mongodb://127.0.0.1:27117]
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
BILLING = HERE.parents[1]
sys.path.insert(0, str(BILLING / "recon"))

import recon

UNITS_PATH = BILLING / "units" / "units.json"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--unit", default="U1")
    p.add_argument("--out", default=None, help="report path (default: <this dir>/<unit>.fixture.recon.json)")
    p.add_argument("--mongo-uri", default=None, help="loopback mongod to load the copy into (default: in-memory)")
    p.add_argument("--seed", type=int, default=recon.DEFAULT_SEED)
    args = p.parse_args(argv)

    units = recon.load_json(UNITS_PATH)
    unit = next((u for u in units["units"] if u["id"] == args.unit), None)
    if unit is None:
        raise SystemExit(f"{args.unit} is not a unit in {UNITS_PATH}")
    collections = list(unit["collections"])
    out = Path(args.out) if args.out else HERE / f"{args.unit}.fixture.recon.json"

    inputs = recon.build_inputs()
    now = dt.datetime.now(recon.UTC).replace(microsecond=0)
    tables = recon.build_faithful_copy(inputs, args.seed)
    docs = recon.load_documents(inputs, tables, now)
    docs = {k: v for k, v in docs.items() if k in collections}
    tables = {t: rows for t, rows in tables.items()
              if t in {c.table for c in inputs.collections if c.name in collections}}
    print(f"{args.unit}: {len(collections)} collections {collections}; synthetic copy "
          f"{sum(len(v) for v in tables.values())} rows in {sorted(tables)} -> {sum(len(v) for v in docs.values())} documents")

    source = recon.DictSource(tables, {"system": "oracle", "mode": "fixture", "schema": "OW_BILLING",
                                       "driver": "synthetic copy of migration/billing/fixtures/demo.json", "seed": args.seed})
    if args.mongo_uri:
        host = urlparse(args.mongo_uri if "://" in args.mongo_uri else f"mongodb://{args.mongo_uri}").hostname or ""
        if host not in recon.LOCAL_HOSTS:
            raise SystemExit("fixture recon only loads into a loopback mongod; it never touches Atlas")
        target = recon.MutableMongoTarget(args.mongo_uri, f"ow_recon_fixture_{args.unit.lower()}", None)
        target.load(docs)
    else:
        target = recon.MutableDictTarget(docs)
    try:
        run = recon.ReconRun(inputs, source, target, "fixture", now=now, collections=collections)
        idem = recon.execute(run)
        namespace = (inputs.fixture or {}).get("namespace", "demo")
        report = recon.build_report(run, namespace, idem, {
            "wave_readiness": {"plan_step": "s4.1.0-preflight", "unit": args.unit, "ticket": unit.get("ticket"),
                               "collections": collections, "units_json": "migration/billing/units/units.json"}})
        path = recon.write_report(report, out)
        errors = recon.validate_report(report)
    finally:
        if isinstance(target, recon.MutableMongoTarget):
            target.drop()
    print(f"recon {run.run_mode}: verdict={run.verdict()} checks={len(run.checks)} "
          f"failed={report['summary']['failed_check_ids'][:8]} -> {path}")
    if errors:
        print("report does not validate against recon-report.schema.json:\n  " + "\n  ".join(errors))
        return 2
    print(f"merge_evidence={report['merge_evidence']} ({report['merge_evidence_note']})")
    return 0 if run.verdict() == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
