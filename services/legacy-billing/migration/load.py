"""Load one migration unit from OW_BILLING (read-only) into the ow_billing MongoDB database.

    python -m services.legacy-billing.migration.load --unit invoices

Units and their collections are declared in units.json next to this file. The mapping spec
(.migration/03_mapping_spec.json) is the single description of how each Oracle column
becomes a document field; this loader only executes it. Each run drops and reloads the
unit's collections, so a rerun is idempotent. Writes go only to the database named on the
command line, which must be allowlisted in .migration/allowed_targets.json.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .common import LoaderError, load_collection, load_mapping, mongo_database, oracle_connection

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def unit_collections(unit: str) -> list[str]:
    units = json.loads((HERE / "units.json").read_text())
    if unit not in units:
        raise LoaderError(f"unknown unit '{unit}'; known: {', '.join(sorted(units))}")
    return units[unit]["collections"]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--unit", required=True)
    p.add_argument("--spec", type=Path, default=REPO / ".migration/03_mapping_spec.json")
    p.add_argument("--allowed-targets", type=Path, default=REPO / ".migration/allowed_targets.json")
    p.add_argument("--target-db", default="ow_billing")
    p.add_argument("--source-dsn-secret", default="ORACLE_BILLING_DSN")
    p.add_argument("--target-uri-secret", default="MONGO_LOCAL_URI")
    p.add_argument("--log", type=Path, help="write the load counts as JSON here")
    args = p.parse_args(argv)

    try:
        names = unit_collections(args.unit)
        version, mapping = load_mapping(args.spec)
        db = mongo_database(args.target_db, args.allowed_targets, args.target_uri_secret)
        conn = oracle_connection(args.source_dsn_secret)
    except LoaderError as exc:
        print(f"load: {exc}", file=sys.stderr)
        return 2

    started = time.time()
    results = {}
    for name in names:
        cmap = mapping[name]
        t0 = time.time()
        counts = load_collection(conn, db, cmap)
        counts["seconds"] = round(time.time() - t0, 2)
        results[name] = counts
        embedded = f", {counts['embedded_elements']} embedded" if counts["embedded_elements"] else ""
        raw = f", {counts['unparseable_dates']} unparseable dates kept in *_raw" if counts["unparseable_dates"] else ""
        attrs = f", {counts['attached_attributes']} attributes attached" if counts["attached_attributes"] else ""
        print(f"{name:<20} <- {cmap.root_table:<22} {counts['documents']:>7} docs{embedded}{raw}{attrs} ({counts['seconds']}s)")
    conn.close()

    summary = {"unit": args.unit, "mapping_version": version, "target_db": args.target_db,
               "collections": results, "seconds": round(time.time() - started, 2)}
    print(f"unit {args.unit}: {len(names)} collections loaded into {args.target_db} "
          f"(mapping {version}, {summary['seconds']}s)")
    if args.log:
        args.log.parent.mkdir(parents=True, exist_ok=True)
        args.log.write_text(json.dumps(summary, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
