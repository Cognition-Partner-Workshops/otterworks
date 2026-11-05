"""Validate workloads/<id>/provenance.yaml against the schema and the attribution rules.

Usage: validate_provenance.py [PATH ...]   (default: every workloads/*/provenance.yaml)
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import jsonschema
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sf_attribution as sf  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = Path(__file__).resolve().parent / "provenance.schema.json"


class _StringDateLoader(yaml.SafeLoader):
    """SafeLoader that keeps dates and timestamps as the strings that were written."""


_StringDateLoader.yaml_implicit_resolvers = {
    key: [(tag, regexp) for tag, regexp in resolvers if tag != "tag:yaml.org,2002:timestamp"]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def load(path: Path) -> object:
    return yaml.load(path.read_text(), Loader=_StringDateLoader)


def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def _carries_run_token(obj: dict) -> bool:
    name = obj["name"]
    if sf.RUN_TOKEN in name and sf.EXPIRES.replace("-", "") in name:
        return True
    try:
        comment = json.loads(obj.get("comment", ""))
    except json.JSONDecodeError:
        return False
    return isinstance(comment, dict) and comment.get("run_token") == sf.RUN_TOKEN and comment.get("expires") == sf.EXPIRES


def _expected_names(workload: str) -> dict[str, str]:
    return {
        "database": sf.database_name(workload),
        "schema": f"{sf.database_name(workload)}.{sf.APP_SCHEMA}",
        "warehouse": sf.warehouse_name(workload),
        "resource_monitor": sf.resource_monitor_name(workload),
        "task": sf.task_name(workload),
        "streamlit": sf.streamlit_name(workload),
    }


def validate(doc: object, path: Path | None = None) -> list[str]:
    validator = jsonschema.Draft202012Validator(schema(), format_checker=jsonschema.FormatChecker())
    errors = [
        f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
        for e in sorted(validator.iter_errors(doc), key=lambda e: list(map(str, e.absolute_path)))
    ]
    if errors:
        return errors
    assert isinstance(doc, dict)
    monitor = doc["warehouse"]["resource_monitor"]
    if "administrative_change" in monitor and monitor["administrative_change"]["to"] != monitor["credit_quota"]:
        errors.append("warehouse/resource_monitor/administrative_change/to: must match recorded credit_quota")
    deployment = doc.get("deployment")
    if deployment:
        times = [("attempted/started_at", deployment["attempted"]["started_at"]),
                 ("attempted/finished_at", deployment["attempted"]["finished_at"])]
        if deployment["deployed"]:
            times.append(("deployed/deployed_at", deployment["deployed"]["deployed_at"]))
        installed_keys = set()
        for i, entry in enumerate(deployment.get("installed", [])):
            times.append((f"installed/{i}/installed_at", entry["installed_at"]))
            key = (entry["type"], entry["name"])
            if key in installed_keys:
                errors.append(f"deployment/installed/{i}: duplicate type+name")
            installed_keys.add(key)
        for field, value in times:
            try:
                timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
                valid = timestamp.utcoffset() == timedelta(0) and "T" in value
            except ValueError:
                valid = False
            if not valid:
                errors.append(f"deployment/{field}: expected a valid UTC ISO timestamp")
    if "data_quality" in doc:
        quality = doc["data_quality"]
        for field, value in (
            ("ran_at", quality["ran_at"]),
            ("refresh_task_run/scheduled_time", quality["refresh_task_run"]["scheduled_time"]),
        ):
            try:
                timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
                valid = timestamp.utcoffset() == timedelta(0) and "T" in value
            except ValueError:
                valid = False
            if not valid:
                errors.append(f"data_quality/{field}: expected a valid UTC ISO timestamp")
    workload = doc["workload"]

    if path is not None and path.parent.name != workload:
        errors.append(f"workload: {workload!r} does not match its directory {path.parent.name!r}")
    if doc["run_token"] != sf.RUN_TOKEN:
        errors.append(f"run_token: expected {sf.RUN_TOKEN}, got {doc['run_token']}")
    if doc["expires"] != sf.EXPIRES:
        errors.append(f"expires: expected {sf.EXPIRES}, got {doc['expires']}")

    csids = [e["csid"] for e in doc["endpoints"]]
    for i, ep in enumerate(doc["endpoints"]):
        try:
            sf.Endpoint.from_csid(ep["csid"], workload)
        except sf.AttributionError as err:
            errors.append(f"endpoints/{i}/csid: {err}")
            continue
        if ep["service_user"] != sf.service_user(ep["csid"]):
            errors.append(f"endpoints/{i}/service_user: expected {sf.service_user(ep['csid'])}, got {ep['service_user']}")
    registered = sf.workload_csids(workload)
    if not registered:
        errors.append(f"workload {workload!r} has no registered endpoints in sf_attribution.ENDPOINTS")
    elif sorted(csids) != registered:
        errors.append(f"endpoints: {sorted(csids)} differ from the registered endpoints {registered}")

    expected = _expected_names(workload)
    for i, change in enumerate(doc.get("configuration_changes", [])):
        migration = Path(change["migration"])
        if migration.parent != Path("workloads") / workload / "migrations" or not (ROOT / migration).is_file():
            errors.append(f"configuration_changes/{i}/migration: expected an existing workload migration")
        if change["object"] not in {obj["name"] for obj in doc["objects"]}:
            errors.append(f"configuration_changes/{i}/object: not a recorded workload object")
        for j, evidence in enumerate(change["evidence"]):
            try:
                timestamp = datetime.fromisoformat(evidence["time"].replace("Z", "+00:00"))
                valid = timestamp.utcoffset() == timedelta(0) and "T" in evidence["time"]
            except ValueError:
                valid = False
            if not valid:
                errors.append(f"configuration_changes/{i}/evidence/{j}/time: expected a valid UTC ISO timestamp")
    wh = doc["warehouse"]
    if wh["name"] != expected["warehouse"]:
        errors.append(f"warehouse/name: expected {expected['warehouse']}, got {wh['name']}")
    if wh["resource_monitor"]["name"] != expected["resource_monitor"]:
        errors.append(
            f"warehouse/resource_monitor/name: expected {expected['resource_monitor']}, got {wh['resource_monitor']['name']}"
        )

    tag_value = sf.devin_csid_value(csids) if not any("csid" in e for e in errors) else None
    by_type: dict[str, list[dict]] = {}
    for i, obj in enumerate(doc["objects"]):
        by_type.setdefault(obj["type"], []).append(obj)
        if not _carries_run_token(obj):
            errors.append(
                f"objects/{i} ({obj['name']}): needs run token {sf.RUN_TOKEN} and expiry {sf.EXPIRES} in its name or comment"
            )
        if obj["type"] in sf.TAGGED_OBJECT_TYPES:
            if "devin_csid" not in obj:
                errors.append(f"objects/{i} ({obj['name']}): {obj['type']} must carry DEVIN_CSID")
            elif tag_value and obj["devin_csid"] != tag_value:
                errors.append(f"objects/{i} ({obj['name']}): DEVIN_CSID {obj['devin_csid']!r} should be {tag_value!r}")
        raw_schema = obj["type"] == "schema" and obj["name"] == f"{sf.database_name(workload)}.RAW"
        if obj["type"] in expected and obj["name"] != expected[obj["type"]] and not raw_schema:
            errors.append(f"objects/{i}: {obj['type']} should be named {expected[obj['type']]}, got {obj['name']}")
        if obj["type"] == "user" and obj["name"] not in {sf.service_user(c) for c in csids if sf.CSID_RE.match(c)}:
            errors.append(f"objects/{i}: user {obj['name']} is not the service user of an endpoint")
        if obj["state"] == "provisioned" and doc["source"]["commit"] == sf.PENDING:
            errors.append(f"objects/{i} ({obj['name']}): provisioned objects need source/commit, not pending")
    for kind in sf.TAGGED_OBJECT_TYPES + ("schema", "resource_monitor"):
        if kind not in by_type:
            errors.append(f"objects: missing the workload {kind}")
    users = {o["name"] for o in by_type.get("user", [])}
    for c in csids:
        if sf.CSID_RE.match(c) and sf.service_user(c) not in users:
            errors.append(f"objects: missing service user {sf.service_user(c)}")
    return errors


def main(argv: list[str] | None = None) -> int:
    paths = [Path(p) for p in (argv if argv is not None else sys.argv[1:])]
    if not paths:
        paths = sorted(ROOT.glob("workloads/*/provenance.yaml"))
    if not paths:
        print("no provenance files found", file=sys.stderr)
        return 1
    failed = 0
    for path in paths:
        errors = validate(load(path), path.resolve())
        label = path.resolve().relative_to(ROOT) if path.resolve().is_relative_to(ROOT) else path
        if errors:
            failed += 1
            print(f"FAIL {label}")
            for err in errors:
                print(f"  {err}")
        else:
            print(f"ok   {label}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
