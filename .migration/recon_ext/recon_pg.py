"""`recon run` equivalent for the `postgres` family (D13).

Same arguments as the harness CLI; the only differences are the source adapter
(`PostgresSourceAdapter`) and `--unit-only`, which restricts the mapping to that unit's
collections (the run-wide spec lists every unit). Engine, tiers, tolerances and report
are the harness's own and are called unchanged.

    python3 .migration/recon_ext/recon_pg.py --unit U3 --mapping .migration/03_mapping_spec.json ...
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from postgres_source import PostgresSourceAdapter  # noqa: E402
from recon.adapters import MongoTargetAdapter  # noqa: E402
from recon.config import load_canon_rules, load_mapping_spec, load_tolerances  # noqa: E402
from recon.engine import MODES, run_recon  # noqa: E402


def unit_mapping(mapping: Path, unit: str, out: Path) -> Path:
    data = json.loads(mapping.read_text())
    kept = [c for c in data.get("collections", []) if c.get("unit") == unit]
    if not kept:
        raise SystemExit(f"mapping {mapping} has no collections for unit {unit}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({**data, "collections": kept}, indent=2) + "\n")
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="recon_pg")
    p.add_argument("--unit", required=True)
    p.add_argument("--family", default="postgres", choices=("postgres",))
    p.add_argument("--mapping", required=True, type=Path)
    p.add_argument("--tolerances", required=True, type=Path)
    p.add_argument("--canonicalization", required=True, type=Path)
    p.add_argument("--mode", required=True, choices=MODES)
    p.add_argument("--source-dsn-secret", required=True)
    p.add_argument("--target-uri-secret", required=True)
    p.add_argument("--target-db", required=True)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--param", action="append", default=[], metavar="NAME=VALUE")
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--unit-only", action="store_true",
                   help="restrict the mapping to collections whose unit == --unit "
                        "(written to <out>/mapping/<unit lower>.json)")
    args = p.parse_args(argv)

    params = {}
    for item in args.param:
        name, sep, value = item.partition("=")
        if not sep or not name:
            raise SystemExit(f"--param must be NAME=VALUE, got '{item}'")
        params[name] = value

    mapping = args.mapping
    if args.unit_only:
        mapping = unit_mapping(args.mapping, args.unit,
                               args.out / "mapping" / f"{args.unit.lower()}.json")
    spec = load_mapping_spec(mapping, params)
    tol = load_tolerances(args.tolerances)
    rules = load_canon_rules(args.canonicalization)

    source = PostgresSourceAdapter(args.source_dsn_secret)
    target = MongoTargetAdapter(args.target_uri_secret, args.target_db)
    result = run_recon(args.unit, args.mode, spec, tol, rules, source, target,
                       out_dir=args.out, seed=args.seed, params=params)
    print(f"recon {result['verdict']}: unit={args.unit} mode={args.mode} family=postgres "
          f"mapping={spec.version} tolerances={tol.version} -> {args.out}/result.json")
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
