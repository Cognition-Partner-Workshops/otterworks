"""`recon run` equivalent for U8 (PKG_INVOICING → ow_billing.invoicing).

Tiers 1-3 grade the `replay_u8_*` clone against the Oracle fixture through the
approved mapping. Tier 4 replays the six immutable invoicing transcripts against
the clone; the source side is the recorded Oracle transcript.
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
from ow_billing import invoicing

PREFIX = "replay_u8_"
GRADED_SOURCES = (
    "subscriptions",
    "usage_events",
    "rating_periods",
    "plans",
    "billing_invoices",
    "credit_notes",
)
SCENARIOS = ROOT / "procs" / "scenarios" / "invoicing"
TRANSCRIPTS = ROOT / "procs" / "oracle" / "transcripts" / "invoicing"
PROBE_TYPES = {
    "status": "text",
    "subtotal": "decimal",
    "tax": "decimal",
    "total": "decimal",
}


def unit_mapping(mapping: Path, out: Path) -> Path:
    data = json.loads(mapping.read_text())
    kept = []
    for collection in data.get("collections", []):
        if collection.get("collection") in GRADED_SOURCES:
            kept.append(
                {
                    **collection,
                    "collection": f"{PREFIX}{collection['collection']}",
                    "unit": "U8",
                }
            )
    if len(kept) != len(GRADED_SOURCES):
        raise SystemExit(f"mapping {mapping} lacks one of {GRADED_SOURCES}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({**data, "collections": kept}, indent=2) + "\n")
    return out


def normalize(value: Any, kind: str) -> Any:
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
    for field in fields:
        values = [normalize(row.get(field["from"]), field["type"]) for row in rows]
        out[field["name"]] = values if field.get("collect") else (values[0] if values else None)
    return out


def load_ops() -> list[dict[str, Any]]:
    ops = []
    for path in sorted(SCENARIOS.glob("*.yaml")):
        scenario = yaml.safe_load(path.read_text())
        transcript = json.loads((TRANSCRIPTS / f"{scenario['id']}.json").read_text())
        ops.append(
            {
                "name": scenario["id"],
                "scenario": scenario,
                "transcript": transcript,
                "rules": [],
            }
        )
    return ops


def check_transcript_provenance(ops: list[dict[str, Any]]) -> dict[str, Any]:
    current = oracle_source_sha()
    recorded = {op["transcript"]["oracle_source_sha"] for op in ops}
    return {
        "oracle_source_sha": current,
        "transcripts_match": recorded == {current},
        "scenarios": [op["name"] for op in ops],
    }


def run_source(op: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [dict(op["transcript"]["business_fields"])]
    for probe_id, probe_rows in op["transcript"].get("probes", {}).items():
        rows.extend({"probe": probe_id, **row} for row in probe_rows)
    return rows


def _probe_fields(row: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"name": name, "from": name, "type": PROBE_TYPES[name]}
        for name in row
        if name in PROBE_TYPES
    ]


def make_run_target(store: invoicing.InvoicingStore):
    def run_target(op: dict[str, Any]) -> list[dict[str, Any]]:
        scenario = op["scenario"]
        inputs = {item["name"]: item["value"] for item in scenario["inputs"]}
        tenant = str(inputs.get("tenant_id", ""))
        start = date.fromisoformat(str(inputs["period_start"])) if "period_start" in inputs else None
        end = date.fromisoformat(str(inputs["period_end"])) if "period_end" in inputs else None
        entrypoint = scenario["entrypoint"]

        if entrypoint == "billing.fn_invoice_preview":
            result = invoicing.fn_invoice_preview(store, tenant, start, end)
            return [shape(result, scenario["fields"])]
        if entrypoint == "billing.fn_invoice_lines":
            result = invoicing.fn_invoice_lines(store, str(inputs["invoice_id"]))
            return [shape(result, scenario["fields"])]
        if entrypoint != "billing.sp_issue_invoice":
            raise SystemExit(f"unsupported invoicing entrypoint: {entrypoint}")

        invoicing.sp_issue_invoice(store, tenant, start, end)
        probe_rows = invoicing.invoice_state_rows(store, tenant, start)
        if scenario["fields"][0]["name"] == "credit_ids":
            result_rows = invoicing.credit_note_rows(store, tenant)
        else:
            result_rows = probe_rows
        rows = [shape(result_rows, scenario["fields"])]
        for probe in scenario.get("probes", []):
            if probe["id"] != "invoice_state":
                raise SystemExit(f"unsupported invoicing probe: {probe['id']}")
            transcript_rows = op["transcript"]["probes"].get(probe["id"], [])
            fields = _probe_fields(transcript_rows[0]) if transcript_rows else []
            rows.append({"probe": probe["id"], **shape(probe_rows, fields)})
        return rows

    return run_target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="recon_u8")
    parser.add_argument("--unit", default="U8")
    parser.add_argument("--family", default="oracle", choices=("oracle",))
    parser.add_argument("--mapping", required=True, type=Path)
    parser.add_argument("--tolerances", required=True, type=Path)
    parser.add_argument("--canonicalization", required=True, type=Path)
    parser.add_argument("--mode", required=True, choices=MODES)
    parser.add_argument("--source-dsn-secret", required=True)
    parser.add_argument("--target-uri-secret", required=True)
    parser.add_argument("--target-db", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--param", action="append", default=[], metavar="NAME=VALUE")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)

    params = {}
    for item in args.param:
        name, sep, value = item.partition("=")
        if not sep or not name:
            raise SystemExit(f"--param must be NAME=VALUE, got '{item}'")
        params[name] = value

    mapping = unit_mapping(args.mapping, args.out / "mapping" / f"{args.unit.lower()}.json")
    spec = load_mapping_spec(mapping, params)
    tolerances = load_tolerances(args.tolerances)
    rules = load_canon_rules(args.canonicalization)

    ops = load_ops()
    provenance = check_transcript_provenance(ops)
    if not provenance["transcripts_match"]:
        raise SystemExit(
            f"invoicing transcripts were recorded against another PL/SQL source: {provenance}"
        )

    source = OracleSourceAdapter(args.source_dsn_secret)
    target = MongoTargetAdapter(args.target_uri_secret, args.target_db)
    client = MongoClient(os.environ[args.target_uri_secret])
    store = invoicing.InvoicingStore(client[args.target_db], PREFIX)
    result = run_recon(
        args.unit,
        args.mode,
        spec,
        tolerances,
        rules,
        source,
        target,
        ops=ops,
        run_source=run_source,
        run_target=make_run_target(store),
        out_dir=args.out,
        seed=args.seed,
        params=params,
    )
    (args.out / "tier4_provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(
        f"recon {result['verdict']}: unit={args.unit} mode={args.mode} family=oracle "
        f"mapping={spec.version} tolerances={tolerances.version} -> {args.out}/result.json"
    )
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
