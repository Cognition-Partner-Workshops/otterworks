#!/usr/bin/env python
"""Write unit-scoped copies of the mapping specs for batch w1-b04.

The recon harness grades every collection in the mapping it is given and has no
per-collection filter, while the engagement spec (.migration/03_mapping_spec.json) covers
all six collections owned by five parallel batches. This script copies each contract file
verbatim and keeps only the `collections` entries owned by this batch. No row is modified;
version, notes and canonicalization block are preserved. Contract files are never edited.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
UNITS = {"shares"}

COPIES = {
    ROOT / ".migration/03_mapping_spec.json": HERE / "mapping_spec.w1-b04.json",
    ROOT / "migration/mmp_rt/fixture_mapping_spec.json": HERE / "fixture_mapping_spec.w1-b04.json",
}


def main():
    for src, dst in COPIES.items():
        spec = json.loads(src.read_text())
        spec["collections"] = [c for c in spec["collections"] if c["collection"] in UNITS]
        assert {c["collection"] for c in spec["collections"]} == UNITS, src
        dst.write_text(json.dumps(spec, indent=2) + "\n")
        print(f"{dst.relative_to(ROOT)}: {[c['collection'] for c in spec['collections']]}")


if __name__ == "__main__":
    main()
