"""`recon run` equivalent for U7 (PKG_RATING → ow_billing.rating, D10).

Tiers 1-3 grade the `replay_u7_*` clone against the Oracle fixture through the
approved mapping (the U5/U0 collections the rating module reads or writes, with the
target names prefixed `replay_u7_`; no shape, rule, or tolerance changes). Tier 4
replays the eight immutable rating transcripts (procs/oracle/transcripts/rating) by
running the Python entrypoints against the clone; the source side is the recorded
Oracle transcript, so the legacy estate is never executed or mutated here.

Engine, tiers, tolerances and report are the harness's own and are called unchanged.

    python3 .migration/recon_ext/recon_u7.py --unit U7 --mapping .migration/03_mapping_spec.json ...
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

import yaml
from pymongo import MongoClient
from recon.adapters import MongoTargetAdapter, OracleSourceAdapter
from recon.config import load_canon_rules, load_mapping_spec, load_tolerances
from recon.engine import MODES, run_recon

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "legacy-billing" / "app"))
sys.path.insert(0, str(ROOT / "procs" / "harness"))

from oracle_record import oracle_source_sha
from ow_billing import rating

PREFIX = "replay_u7_"
# Collections the rating module READS are graded against Oracle. `billing_audit_log` is
# a write-only sink for rating (Tier 4 appends to it); its pre-state is the U5 golden copy,
# which was LIVE-graded by the parent against a fixture carrying one observer-caused
# BILLING_AUDIT_LOG row (see 04_progress U5 row) that a fresh `oracle-billing-seed` lacks.
GRADED_SOURCES = ("subscriptions", "usage_events", "rating_periods", "plans")
SCENARIOS = ROOT / "procs" / "scenarios" / "rating"
TRANSCRIPTS = ROOT / "procs" / "oracle" / "transcripts" / "rating"
ENTRYPOINTS = {
    "billing.fn_usage_rating": rating.fn_usage_rating,
    "billing.fn_usage_summary": rating.fn_usage_summary,
}


def unit_mapping(mapping: Path, out: Path) -> Path:
    data = json.loads(mapping.read_text())
    kept = []
    for c in data.get("collections", []):
        if c.get("collection") in GRADED_SOURCES:
            kept.append({**c, "collection": f"{PREFIX}{c['collection']}", "unit": "U7"})
    if len(kept) != len(GRADED_SOURCES):
        raise SystemExit(f"mapping {mapping} lacks one of {GRADED_SOURCES}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({**data, "collections": kept}, indent=2) + "\n")
    return out


def normalize(value: Any, kind: str) -> Any:
    """procs/harness/replay.py normalization: the transcript's field types."""
    if value is None:
        return None
    if kind == "decimal":
        return str(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    if kind == "integer":
        return int(value)
    if kind == "date":
        return date.fromisoformat(str(value)).isoformat()
    return str(value)


def shape(rows: list[dict[str, Any]], fields: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for f in fields:
        values = [normalize(r.get(f["from"]), f["type"]) for r in rows]
        out[f["name"]] = values if f.get("collect") else (values[0] if values else None)
    return out


def load_ops() -> list[dict[str, Any]]:
    ops = []
    for path in sorted(SCENARIOS.glob("*.yaml")):
        scenario = yaml.safe_load(path.read_text())
        transcript = json.loads((TRANSCRIPTS / f"{scenario['id']}.json").read_text())
        ops.append({
            "name": scenario["id"],
            "collection": f"{PREFIX}usage_events" if scenario["kind"] != "procedure"
            else f"{PREFIX}rating_periods",
            "scenario": scenario,
            "transcript": transcript,
            "rules": [],
        })
    return ops


def check_transcript_provenance(ops: list[dict[str, Any]]) -> dict[str, Any]:
    current = oracle_source_sha()
    recorded = {op["transcript"]["oracle_source_sha"] for op in ops}
    return {"oracle_source_sha": current, "transcripts_match": recorded == {current},
            "scenarios": [op["name"] for op in ops]}


def run_source(op: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [dict(op["transcript"]["business_fields"])]
    for probe_id, probe_rows in op["transcript"].get("probes", {}).items():
        rows.extend({"probe": probe_id, **r} for r in probe_rows)
    return rows


def make_run_target(store: rating.RatingStore):
    def run_target(op: dict[str, Any]) -> list[dict[str, Any]]:
        scenario = op["scenario"]
        inputs = {i["name"]: i["value"] for i in scenario["inputs"]}
        tenant = str(inputs["tenant_id"])
        start, end = date.fromisoformat(str(inputs["period_start"])), date.fromisoformat(str(inputs["period_end"]))
        if scenario["entrypoint"] == "billing.sp_finalize_rating":
            rating.sp_finalize_rating(store, tenant, start, end)
            result_rows = rating.rating_result_rows(store, tenant, start)
            rows = [shape(result_rows, scenario["fields"])]
            for probe in scenario.get("probes", []):
                for r in result_rows:
                    rows.append({"probe": probe["id"], **shape([r], scenario["fields"])})
            return rows
        result = ENTRYPOINTS[scenario["entrypoint"]](store, tenant, start, end)
        return [shape(result, scenario["fields"])]
    return run_target


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="recon_u7")
    p.add_argument("--unit", default="U7")
    p.add_argument("--family", default="oracle", choices=("oracle",))
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
    args = p.parse_args(argv)

    params = {}
    for item in args.param:
        name, sep, value = item.partition("=")
        if not sep or not name:
            raise SystemExit(f"--param must be NAME=VALUE, got '{item}'")
        params[name] = value

    mapping = unit_mapping(args.mapping, args.out / "mapping" / f"{args.unit.lower()}.json")
    spec = load_mapping_spec(mapping, params)
    tol = load_tolerances(args.tolerances)
    rules = load_canon_rules(args.canonicalization)

    ops = load_ops()
    provenance = check_transcript_provenance(ops)
    if not provenance["transcripts_match"]:
        raise SystemExit(f"rating transcripts were recorded against another PL/SQL source: {provenance}")

    source = OracleSourceAdapter(args.source_dsn_secret)
    target = MongoTargetAdapter(args.target_uri_secret, args.target_db)
    client = MongoClient(os.environ[args.target_uri_secret])
    store = rating.RatingStore(client[args.target_db], PREFIX)
    result = run_recon(args.unit, args.mode, spec, tol, rules, source, target,
                       ops=ops, run_source=run_source, run_target=make_run_target(store),
                       out_dir=args.out, seed=args.seed, params=params)
    (args.out / "tier4_provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(f"recon {result['verdict']}: unit={args.unit} mode={args.mode} family=oracle "
          f"mapping={spec.version} tolerances={tol.version} -> {args.out}/result.json")
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
