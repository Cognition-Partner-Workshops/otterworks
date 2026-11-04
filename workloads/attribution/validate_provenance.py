"""Validate workloads/<id>/provenance.yaml against the schema and the naming rules.

Usage: validate_provenance.py [PATH ...]   (default: every workloads/*/provenance.yaml)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sf_attribution as attr  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = Path(__file__).resolve().parent / "provenance.schema.json"
TAGGED_TYPES = ("database", "warehouse", "task", "streamlit")


class _StringTimestampLoader(yaml.SafeLoader):
    """SafeLoader that leaves ISO timestamps as strings so the schema sees what was written."""


_StringTimestampLoader.yaml_implicit_resolvers = {
    key: [(tag, regexp) for tag, regexp in resolvers if tag != "tag:yaml.org,2002:timestamp"]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def load(path: Path) -> object:
    return yaml.load(path.read_text(), Loader=_StringTimestampLoader)


def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def _spec_csids(spec_path: Path) -> list[str]:
    spec = yaml.safe_load(spec_path.read_text())
    endpoints = spec.get("endpoints") or [spec.get("endpoint") or {}]
    return [e["client_side_id"] for e in endpoints if e.get("client_side_id")]


def validate(doc: object, path: Path | None = None, root: Path = ROOT) -> list[str]:
    validator = jsonschema.Draft202012Validator(schema())
    errors = [
        f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
        for e in sorted(validator.iter_errors(doc), key=lambda e: list(map(str, e.absolute_path)))
    ]
    if errors:
        return errors
    assert isinstance(doc, dict)
    workload = doc["workload"]

    if path is not None and path.parent.name != workload:
        errors.append(f"workload: {workload!r} does not match its directory {path.parent.name!r}")
    if doc["run_token"] != attr.RUN_TOKEN:
        errors.append(f"run_token: expected {attr.RUN_TOKEN}, got {doc['run_token']}")

    spec_path = root / doc["spec"]
    csids = [e["csid"] for e in doc["endpoints"]]
    if not spec_path.is_file():
        errors.append(f"spec: {doc['spec']} does not exist")
    elif sorted(_spec_csids(spec_path)) != sorted(csids):
        errors.append(f"endpoints: csids {sorted(csids)} differ from the spec's {sorted(_spec_csids(spec_path))}")

    for i, endpoint in enumerate(doc["endpoints"]):
        try:
            attr.Endpoint.from_csid(endpoint["csid"], workload)
        except attr.AttributionError as err:
            errors.append(f"endpoints/{i}/csid: {err}")
            continue
        if endpoint["service_user"] != attr.service_user(endpoint["csid"]):
            errors.append(f"endpoints/{i}/service_user: expected {attr.service_user(endpoint['csid'])}")

    wh = doc["warehouse"]
    if wh["name"] != attr.warehouse_name(workload):
        errors.append(f"warehouse/name: expected {attr.warehouse_name(workload)}")
    if wh["resource_monitor"]["name"] != attr.resource_monitor_name(workload):
        errors.append(f"warehouse/resource_monitor/name: expected {attr.resource_monitor_name(workload)}")

    expected_tag = attr.devin_csid_value(csids)
    objects = doc["deployed_objects"]
    by_type: dict[str, list[str]] = {}
    for i, obj in enumerate(objects):
        by_type.setdefault(obj["type"], []).append(obj["name"])
        if obj["type"] in TAGGED_TYPES and obj["devin_csid"] != expected_tag:
            errors.append(f"deployed_objects/{i}/devin_csid: expected {expected_tag}, got {obj['devin_csid']}")
        if obj["type"] not in TAGGED_TYPES and "devin_csid" in obj:
            errors.append(f"deployed_objects/{i}: a {obj['type']} does not carry DEVIN_CSID")
    expected_single = {
        "warehouse": attr.warehouse_name(workload),
        "database": attr.database_name(workload),
        "resource_monitor": attr.resource_monitor_name(workload),
    }
    for kind, name in expected_single.items():
        if by_type.get(kind) != [name]:
            errors.append(f"deployed_objects: expected exactly one {kind} {name}, got {by_type.get(kind, [])}")
    users = sorted(attr.service_user(c) for c in csids)
    if sorted(by_type.get("user", [])) != users:
        errors.append(f"deployed_objects: expected users {users}, got {sorted(by_type.get('user', []))}")
    for kind in ("task", "streamlit"):
        for name in by_type.get(kind, []):
            if not name.startswith(attr.database_name(workload) + "."):
                errors.append(f"deployed_objects: {kind} {name} is outside {attr.database_name(workload)}")

    usage = doc["usage"]
    figures = {k: v for k, v in usage.items() if k not in ("source", "reported_through")}
    if usage["reported_through"] == attr.PENDING:
        reported = sorted(k for k, v in figures.items() if v != attr.PENDING)
        if reported:
            errors.append(f"usage: reported_through is pending but {reported} carry figures")
    return errors


def main(argv: list[str] | None = None) -> int:
    paths = [Path(p) for p in (argv if argv is not None else sys.argv[1:])]
    if not paths:
        paths = sorted((ROOT / "workloads").glob("*/provenance.yaml"))
    if not paths:
        print("no provenance.yaml files found", file=sys.stderr)
        return 1
    failed = 0
    for path in paths:
        errors = validate(load(path), path.resolve())
        rel = path.resolve().relative_to(ROOT) if path.resolve().is_relative_to(ROOT) else path
        if errors:
            failed += 1
            print(f"FAIL {rel}")
            for err in errors:
                print(f"  {err}")
        else:
            print(f"ok   {rel}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
