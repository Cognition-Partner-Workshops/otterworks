"""Render the canonical <unit>.recon.json from the harness result.json for one unit.

Usage: python3 -m services.legacy-billing.migration.recon_report --unit w1-dunning
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

LIVE_RECON = "live recon: not run, no source access"
UNVERIFIED = [
    "live/snapshot recon against a customer source (no source access in offline mode)",
    "write paths (history triggers, pkg_* procedures) are not exercised by this loader",
]


def render(result: dict) -> dict:
    return {
        "kind": "recon-report",
        "unit": result["unit"],
        "mode": result["mode"],
        "verdict": result["verdict"],
        "merge_eligible": False,
        "merge_eligible_reason": "fixture evidence",
        "live_recon": LIVE_RECON,
        "tolerance_version": result["tolerance_version"],
        "mapping_version": result["mapping_version"],
        "redacted": result["redacted"],
        "generated_at": result["generated_at"],
        "tiers": result["tiers"],
        "unverified_paths": UNVERIFIED,
        "source": "result.json",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--unit", required=True)
    ap.add_argument("--recon-dir", default=".migration/recon")
    args = ap.parse_args()
    unit_dir = Path(args.recon_dir) / args.unit
    result = json.loads((unit_dir / "result.json").read_text())
    out = unit_dir / f"{args.unit}.recon.json"
    out.write_text(json.dumps(render(result), indent=2) + "\n")
    print(f"{out}: {result['verdict']} generated_at={result['generated_at']}")


if __name__ == "__main__":
    main()
