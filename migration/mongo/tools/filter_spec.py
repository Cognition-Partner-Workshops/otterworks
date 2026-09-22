#!/usr/bin/env python3
"""Derive a unit-scoped mapping spec from .migration/03_mapping_spec.json.

`recon run --unit` is a label only: the harness grades every collection in
the spec it is handed. Per-unit evidence therefore needs a spec filtered to
exactly that unit's collections. This script never edits the spec; it writes
a derived copy under .migration/recon/<unit>/mapping.<unit>.json.

Usage: filter_spec.py --unit <name> --collections codes tenants ...
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SPEC = REPO_ROOT / ".migration" / "03_mapping_spec.json"


def filter_spec(spec_path: Path, collection_names: list[str], out: Path) -> Path:
    spec = json.loads(spec_path.read_text())
    wanted = set(collection_names)
    spec["collections"] = [c for c in spec["collections"]
                           if c["collection"] in wanted]
    found = {c["collection"] for c in spec["collections"]}
    missing = wanted - found
    if missing:
        raise SystemExit(f"collections not in spec: {sorted(missing)}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(spec, indent=2) + "\n")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--unit", required=True)
    ap.add_argument("--collections", nargs="+", required=True)
    args = ap.parse_args()
    out = REPO_ROOT / ".migration" / "recon" / args.unit / f"mapping.{args.unit}.json"
    filter_spec(SPEC, args.collections, out)
    print(f"wrote {out} ({len(args.collections)} collections)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
