#!/usr/bin/env python3
"""UNT-22: read-only comparison of the batch loader's mapped documents against what is in Atlas.

Builds the documents the PR head's migration/billing/loaders/oracle_to_mongo.py would load (its own
`build_documents`, fed by recon.OracleSource over the read-only live DSN) for the given collections and
compares them, document by document and field by field, with the documents already in the migration
database on Atlas. Nothing is written anywhere: the Mongo client is used for find() only and the Oracle
session is SET TRANSACTION READ ONLY (recon.OracleSource). Fields the loader derives from "now"
(quarantine capturedAt) are detected by building the documents twice with two clocks and excluded.

    uv run --no-project --with oracledb==2.5.1 --with pymongo==4.10.1 \
      python3 migration/billing/waves/wave2/verify/loader_vs_atlas.py --repo-root <PR checkout> \
        --collections rating_periods,usage_events --out <report.json>
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path


def differing_paths(a, b, prefix=""):
    """Paths whose values (or BSON types) differ between two documents."""
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            path = f"{prefix}.{key}" if prefix else key
            if key not in a or key not in b:
                out.append(path)
            else:
                out.extend(differing_paths(a[key], b[key], path))
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{prefix}[len {len(a)}!={len(b)}]"]
        for i, (x, y) in enumerate(zip(a, b)):
            out.extend(differing_paths(x, y, f"{prefix}[{i}]"))
        return out
    if type(a) is not type(b) or a != b:
        return [prefix]
    return []


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--repo-root", required=True)
    p.add_argument("--collections", required=True)
    p.add_argument("--oracle-dsn-env", default="OW_TP_ORACLE_RO_DSN")
    p.add_argument("--mongo-uri-env", default="MONGODB_ATLAS_URI")
    p.add_argument("--out", required=True)
    args = p.parse_args(argv)
    root = Path(args.repo_root).resolve()
    sys.path.insert(0, str(root / "migration/billing/loaders"))
    sys.path.insert(0, str(root / "migration/billing/recon"))
    import recon
    import oracle_to_mongo as loader
    from pymongo import MongoClient

    inputs = recon.build_inputs(root / "migration/billing/mapping_spec.json", root / "migration/billing/tolerances.json", None)
    tol = inputs.tolerances
    schema = tol.get("source", {}).get("schema", "OW_BILLING")
    database = inputs.spec["target"]["database"]
    names = [n.strip() for n in args.collections.split(",") if n.strip()]
    maps = loader._collection_maps(inputs, names)
    source = recon.OracleSource(recon._require_env(args.oracle_dsn_env), args.oracle_dsn_env, schema, 1)
    client = MongoClient(recon._require_env(args.mongo_uri_env), tz_aware=True, appname="unt22-loader-vs-atlas", readPreference="secondaryPreferred")
    db = client[database]
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=root).stdout.strip()
    t1 = dt.datetime(2000, 1, 1, tzinfo=dt.timezone.utc)
    t2 = dt.datetime(2001, 1, 1, tzinfo=dt.timezone.utc)
    report = {"kind": "loader-vs-atlas", "run_mode": "live-readonly", "merge_evidence": False, "writes": "none (find() and SET TRANSACTION READ ONLY only)",
              "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "code_under_test": {"repo_root": str(root), "head": head}, "source": source.describe(),
              "target": {"database": database, "uri_secret": args.mongo_uri_env}, "collections": {}}
    all_ok = True
    for cm in maps:
        docs1, stats = loader.build_documents(source, inputs, cm, t1)
        docs2, _ = loader.build_documents(source, inputs, cm, t2)
        by_id1 = {d["_id"]: d for d in docs1}
        by_id2 = {d["_id"]: d for d in docs2}
        clock_fields = sorted({path for i, d in by_id1.items() for path in differing_paths(d, by_id2[i])})
        atlas = {d["_id"]: d for d in db[cm.name].find({})}
        only_loader = sorted(set(by_id1) - set(atlas), key=str)
        only_atlas = sorted(set(atlas) - set(by_id1), key=str)
        mismatched = {}
        for i in set(by_id1) & set(atlas):
            paths = [path for path in differing_paths(by_id1[i], atlas[i]) if not any(path == c or path.startswith(c + ".") for c in clock_fields)]
            if paths:
                mismatched[str(i)] = paths
        types = {}
        for d in by_id1.values():
            for k, v in d.items():
                types.setdefault(k, set()).add(type(v).__name__)
        entry = {"table": stats["table"], "source_rows": stats["source_rows"], "embedded": stats.get("embedded"),
                 "loader_documents": len(by_id1), "atlas_documents": len(atlas), "clock_dependent_fields_excluded": clock_fields,
                 "only_in_loader": only_loader[:20], "only_in_loader_count": len(only_loader), "only_in_atlas": only_atlas[:20], "only_in_atlas_count": len(only_atlas),
                 "mismatched_documents": dict(list(mismatched.items())[:20]), "mismatched_count": len(mismatched),
                 "loader_field_types": {k: sorted(v) for k, v in sorted(types.items())},
                 "identical": not only_loader and not only_atlas and not mismatched and len(by_id1) == len(atlas) > 0}
        all_ok = all_ok and entry["identical"]
        report["collections"][cm.name] = entry
        print(f"{cm.name}: loader {len(by_id1)} vs atlas {len(atlas)} documents, only_loader {len(only_loader)}, only_atlas {len(only_atlas)}, "
              f"mismatched {len(mismatched)} -> {'identical' if entry['identical'] else 'DIFFERENT'}")
    client.close()
    report["verdict"] = "identical" if all_ok else "different"
    Path(args.out).write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(f"{report['verdict']} -> {args.out}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
