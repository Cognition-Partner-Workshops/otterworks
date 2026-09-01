#!/usr/bin/env python3
"""D13 runner: execute the official mongo-recon-harness engine for a DynamoDB-sourced unit.

Mirrors `recon run` exactly (same config loaders, engine, report writer, exit code); the
only extension is the source adapter, which the stock CLI cannot construct for DynamoDB.
The unit's collections are selected from the frozen mapping spec by `unit`; the filtered
copy is written next to the evidence for citation, with mapping shapes unchanged.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from recon.adapters import MongoTargetAdapter
from recon.config import load_canon_rules, load_mapping_spec, load_tolerances
from recon.engine import MODES, run_recon

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dynamo_source import DynamoSourceAdapter  # noqa: E402


def _unit_mapping(spec_path: Path, unit: str, out_path: Path) -> Path:
    data = json.loads(spec_path.read_text())
    cols = [c for c in data["collections"] if c.get("unit") == unit]
    if not cols:
        raise SystemExit(f"{spec_path}: no collections assigned to {unit}")
    if any(c.get("family") != "dynamodb" for c in cols):
        raise SystemExit(f"{unit} has non-dynamodb collections; use the stock `recon run`")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({**data, "collections": cols}, indent=2) + "\n")
    return out_path


def _field_types(mapping_path: Path) -> dict[str, dict[str, tuple[str, str]]]:
    types: dict[str, dict[str, tuple[str, str]]] = {}
    for c in json.loads(mapping_path.read_text())["collections"]:
        t = types.setdefault(c["root_table"], {})
        for f in c["fields"]:
            t[f["source"]] = (f.get("source_type", "S"), f.get("bson_type", "string"))
    return types


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="run_dynamo_recon")
    p.add_argument("--unit", required=True)
    p.add_argument("--mapping", required=True, type=Path)
    p.add_argument("--tolerances", required=True, type=Path)
    p.add_argument("--canonicalization", required=True, type=Path)
    p.add_argument("--mode", required=True, choices=MODES)
    p.add_argument("--source-endpoint-secret", default="AWS_ENDPOINT_URL",
                   help="ENV VAR NAME holding the DynamoDB endpoint URL")
    p.add_argument("--target-uri-secret", required=True)
    p.add_argument("--target-db", required=True)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--param", action="append", default=[], metavar="NAME=VALUE")
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args(argv)

    params = {}
    for item in args.param:
        name, sep, value = item.partition("=")
        if not sep or not name:
            raise SystemExit(f"--param must be NAME=VALUE, got '{item}'")
        params[name] = value

    unit_mapping = _unit_mapping(
        args.mapping, args.unit, args.out.parent / "mapping" / f"{args.unit.lower()}.json")
    spec = load_mapping_spec(unit_mapping, params)
    tol = load_tolerances(args.tolerances)
    rules = load_canon_rules(args.canonicalization)

    source = DynamoSourceAdapter(_field_types(unit_mapping), args.source_endpoint_secret)
    target = MongoTargetAdapter(args.target_uri_secret, args.target_db)
    result = run_recon(args.unit, args.mode, spec, tol, rules, source, target,
                       out_dir=args.out, seed=args.seed, params=params)
    print(f"recon {result['verdict']}: unit={args.unit} mode={args.mode} "
          f"mapping={spec.version} tolerances={tol.version} -> {args.out}/result.json")
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
