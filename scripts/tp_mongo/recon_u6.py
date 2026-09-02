"""Run the U6 fixture recon, including Tier 4 application replay."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

import yaml
from pymongo import MongoClient

from load_replay_u6 import PREFIX, TARGET_DB

ROOT = Path(__file__).resolve().parents[2]
MAPPING_SOURCE = ROOT / ".migration/03_mapping_spec.json"
MAPPING_OUT = ROOT / ".migration/recon/U6/mapping/u6.json"
TOLERANCES = ROOT / ".migration/02_tolerances.json"
CANONICALIZATION = ROOT / ".migration/canonicalization.json"
ROUTES = ROOT / "procs/routes.yaml"
OUT_DIR = ROOT / ".migration/recon/U6"
TIER4_OUT = OUT_DIR / "tier4_replay.json"
SEED = 714559852
PARAMS = {"batch_no": "85559852", "source_ns": "demo"}
BASELINE_TENANTS = {
    "00000000-0000-0000-0000-000000000001": (
        "20000000-0000-0000-0000-000000000001",
    ),
    "00000000-0000-0000-0000-000000000004": (
        "20000000-0000-0000-0000-000000000004",
    ),
}
TIER4_ROWS: list[dict[str, Any]] = []


def extract(payload: Any, json_path: str) -> Any:
    """Extract the two JSONPath forms used by the billing route contract."""
    if json_path.startswith("$.") and "[*]" not in json_path:
        value = payload
        for part in json_path[2:].split("."):
            if value is None or not isinstance(value, dict):
                return None
            value = value.get(part)
        return value
    if json_path.startswith("$[*]."):
        field = json_path[5:]
        if payload is None:
            return []
        if not isinstance(payload, list):
            raise ValueError(f"JSONPath {json_path!r} requires an array response")
        return [item.get(field) if isinstance(item, dict) else None for item in payload]
    raise ValueError(f"unsupported JSONPath: {json_path}")


def _normalize(value: Any, field: dict[str, Any]) -> Any:
    if value is None:
        return None
    field_type = field.get("type", "rows")
    if field.get("collect"):
        return [_normalize_scalar(item, field_type) for item in value]
    return _normalize_scalar(value, field_type)


def _normalize_scalar(value: Any, field_type: str) -> Any:
    if value is None:
        return None
    if field_type == "rows":
        return value
    if field_type == "decimal":
        return str(
            Decimal(str(value)).quantize(
                Decimal("0.01"),
                ROUND_HALF_UP,
            )
        )
    if field_type == "integer":
        return int(value)
    if field_type == "text":
        return str(value)
    return value


def flatten(values: dict[str, Any]) -> dict[str, str]:
    return {
        f"{group}.{key}": json.dumps(value, sort_keys=True)
        for group in ("business_fields", "probes")
        for key, value in values.get(group, {}).items()
    }


def _route_entrypoint(name: str) -> dict[str, Any]:
    routes = yaml.safe_load(ROUTES.read_text())
    return routes["modules"]["plans"]["entrypoints"][name]


def extract_response(op: dict[str, Any], payload: Any) -> dict[str, dict[str, Any]]:
    contract = _route_entrypoint(op["entrypoint"]).get("response", {})
    expected = {"business_fields": {}, "probes": {}}
    for group in ("business_fields", "probes"):
        for field_name, field in contract.get(group, {}).items():
            expected[group][field_name] = _normalize(
                extract(payload, field["json_path"]) if payload is not None else None,
                field,
            )
    return expected


def _operations() -> list[dict[str, Any]]:
    operations = []
    for number in range(1, 6):
        scenario = f"PLANS-{number:03d}"
        transcript = json.loads(
            (ROOT / "procs/oracle/transcripts/plans" / f"{scenario}.json").read_text()
        )
        operations.append(
            {
                "name": scenario,
                "collection": (
                    "replay_u6_plans"
                    if number <= 3
                    else "replay_u6_subscriptions"
                ),
                "entrypoint": transcript["entrypoint"],
                "inputs": transcript["inputs"],
                "expected": {
                    "business_fields": transcript["business_fields"],
                    "probes": transcript["probes"],
                },
                "rules": [],
            }
        )
    return operations


def run_source(op: dict[str, Any]) -> list[dict[str, str]]:
    return [flatten(op["expected"])]


def run_target(op: dict[str, Any]) -> list[dict[str, str]]:
    from ow_billing import Store
    from ow_billing.routes import call_entrypoint

    uri = os.environ.get("MONGODB_ATLAS_URI")
    if not uri:
        raise RuntimeError("secret MONGODB_ATLAS_URI not set")
    client = MongoClient(uri)
    try:
        store = Store(client, TARGET_DB, PREFIX)
        payload = call_entrypoint(store, op["entrypoint"], op["inputs"])
        actual = extract_response(op, payload)
        source_rows = run_source(op)
        target_rows = [flatten(actual)]
        TIER4_ROWS.append(
            {"name": op["name"], "source": source_rows, "target": target_rows}
        )
        return target_rows
    finally:
        client.close()


def _date(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.date().isoformat()
    return value.isoformat() if hasattr(value, "isoformat") else value


def preflight_baseline(uri: str) -> None:
    client = MongoClient(uri)
    try:
        subscriptions = client[TARGET_DB][f"{PREFIX}subscriptions"]
        for tenant_id, (subscription_id,) in BASELINE_TENANTS.items():
            rows = list(subscriptions.find({"tenant_id": tenant_id}))
            if len(rows) != 1:
                raise RuntimeError(
                    "replay_u6_* clone is not at the fixture baseline; "
                    "re-run load_replay_u6.py before recon"
                )
            row = rows[0]
            expected = {
                "_id": subscription_id,
                "plan_id": "10000000-0000-0000-0000-000000000001",
                "starts_on": "2026-01-01",
                "ends_on": None,
                "status_cd": 10,
            }
            actual = {
                "_id": row.get("_id"),
                "plan_id": row.get("plan_id"),
                "starts_on": _date(row.get("starts_on")),
                "ends_on": _date(row.get("ends_on")),
                "status_cd": row.get("status_cd"),
            }
            if actual != expected:
                raise RuntimeError(
                    "replay_u6_* clone is not at the fixture baseline; "
                    "re-run load_replay_u6.py before recon"
                )
    finally:
        client.close()


def write_mapping() -> Path:
    data = json.loads(MAPPING_SOURCE.read_text())
    selected = set(load_replay_collection_names())
    data["collections"] = [
        {
            **collection,
            "collection": f"{PREFIX}{collection['collection']}",
        }
        for collection in data["collections"]
        if collection["collection"] in selected
    ]
    MAPPING_OUT.parent.mkdir(parents=True, exist_ok=True)
    MAPPING_OUT.write_text(json.dumps(data, indent=2) + "\n")
    return MAPPING_OUT


def load_replay_collection_names() -> tuple[str, ...]:
    from load_replay_u6 import UNIT_COLLECTIONS

    return UNIT_COLLECTIONS


def run() -> dict[str, Any]:
    sys.path.insert(0, str(ROOT / "services/legacy-billing/app"))
    from recon.adapters import MongoTargetAdapter, OracleSourceAdapter
    from recon.config import load_canon_rules, load_mapping_spec, load_tolerances
    from recon.engine import run_recon

    uri = os.environ.get("MONGODB_ATLAS_URI")
    if not uri:
        raise RuntimeError("secret MONGODB_ATLAS_URI not set")
    preflight_baseline(uri)
    mapping_path = write_mapping()
    params = dict(PARAMS)
    spec = load_mapping_spec(mapping_path, params)
    tolerance = load_tolerances(TOLERANCES)
    rules = load_canon_rules(CANONICALIZATION)
    source = OracleSourceAdapter("OW_BILLING_FIXTURE_DSN")
    target = MongoTargetAdapter("MONGODB_ATLAS_URI", TARGET_DB)
    TIER4_ROWS.clear()
    result = run_recon(
        "U6",
        "live",
        spec,
        tolerance,
        rules,
        source,
        target,
        ops=_operations(),
        run_source=run_source,
        run_target=run_target,
        out_dir=OUT_DIR,
        seed=SEED,
        params=params,
    )
    TIER4_OUT.write_text(json.dumps(TIER4_ROWS, indent=2) + "\n")
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(OUT_DIR))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = run()
    print(
        f"recon {result['verdict']}: unit=U6 mode=live mapping="
        f"{result['mapping_version']} tolerances={result['tolerance_version']} "
        f"-> {Path(args.out) / 'result.json'}"
    )
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
