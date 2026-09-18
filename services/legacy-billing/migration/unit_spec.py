"""Write the mapping-spec subset for one unit.

The recon harness grades every collection in the mapping file it is given, so each unit
gets its own subset of .migration/03_mapping_spec.json (same version, same rows, only the
unit's collections). Regenerating the subset is deterministic; the file is committed with
the unit so the recon evidence points at exactly what was graded.

    python -m services.legacy-billing.migration.unit_spec --unit w1-invoices
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .load import HERE, REPO, unit_collections


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--unit", required=True)
    p.add_argument("--spec", type=Path, default=REPO / ".migration/03_mapping_spec.json")
    p.add_argument("--out", type=Path)
    args = p.parse_args(argv)

    names = set(unit_collections(args.unit))
    spec = json.loads(args.spec.read_text())
    subset = dict(spec)
    subset["collections"] = [c for c in spec["collections"] if c["collection"] in names]
    subset["unit"] = args.unit
    subset["derived_from"] = str(args.spec.relative_to(REPO)) if args.spec.is_absolute() else str(args.spec)
    out = args.out or REPO / ".migration/units" / f"{args.unit}.mapping.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(subset, indent=2, sort_keys=False) + "\n")
    print(f"{out.relative_to(REPO)}: {len(subset['collections'])} of {len(spec['collections'])} "
          f"collections, mapping {spec['version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
