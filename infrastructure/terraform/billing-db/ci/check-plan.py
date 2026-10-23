#!/usr/bin/env python3
"""Check the billing-db plan JSON: run tags on every tagged resource, plus the
database settings the billing results depend on.

Equivalent of scripts/check-plan-tags.py from the disposition-modules PR, which
has not landed on demo-appassess; it also reads tags_all because this root
tags through the provider's default_tags.
"""

import argparse
import json
import sys

EXPECTED_PARAMETERS = {
    "rds.force_ssl": "1",
    "timezone": "UTC",
    "datestyle": "ISO, MDY",
}

# Every resource type in this root that accepts tags. A type missing from the
# plan, or one planned without tags, fails the check.
TAGGABLE_TYPES = {
    "aws_cloudwatch_log_group",
    "aws_db_instance",
    "aws_db_parameter_group",
    "aws_db_subnet_group",
    "aws_security_group",
    "aws_vpc_security_group_ingress_rule",
}


def resources(module):
    yield from module.get("resources", [])
    for child in module.get("child_modules", []):
        yield from resources(child)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("plan")
    parser.add_argument("--run-token", required=True)
    parser.add_argument("--expires", required=True)
    parser.add_argument("--engine-version", required=True)
    parser.add_argument("--allowed-cidr", action="append", required=True)
    args = parser.parse_args()

    with open(args.plan, encoding="utf-8") as plan_file:
        plan = json.load(plan_file)
    root = plan.get("planned_values", {}).get("root_module")
    if not isinstance(root, dict):
        raise SystemExit("plan JSON has no planned_values.root_module")

    managed = [r for r in resources(root) if r.get("mode") == "managed"]
    by_type = {}
    for r in managed:
        by_type.setdefault(r["type"], []).append(r)

    failures = []
    tag_rows = []
    for r in managed:
        values = r.get("values") or {}
        if "tags_all" not in values and "tags" not in values:
            if r["type"] in TAGGABLE_TYPES:
                failures.append(f"{r['address']}: taggable type planned without tags")
            continue
        tags = values.get("tags_all") or values.get("tags") or {}
        tag_rows.append((r["address"], tags.get("run_token"), tags.get("Expires")))
        if tags.get("run_token") != args.run_token:
            failures.append(f"{r['address']}: run_token={tags.get('run_token')!r}, expected {args.run_token!r}")
        if tags.get("Expires") != args.expires:
            failures.append(f"{r['address']}: Expires={tags.get('Expires')!r}, expected {args.expires!r}")
    for t in sorted(TAGGABLE_TYPES - by_type.keys()):
        failures.append(f"{t}: expected in the plan, not found")

    settings = []

    def expect(label, actual, wanted):
        ok = actual == wanted
        settings.append((label, actual, "ok" if ok else f"FAILED (expected {wanted!r})"))
        if not ok:
            failures.append(f"{label}: {actual!r}, expected {wanted!r}")

    db = (by_type.get("aws_db_instance") or [{}])[0].get("values", {})
    expect("aws_db_instance.engine", db.get("engine"), "postgres")
    expect("aws_db_instance.engine_version", db.get("engine_version"), args.engine_version)
    expect("aws_db_instance.storage_encrypted", db.get("storage_encrypted"), True)
    expect("aws_db_instance.deletion_protection", db.get("deletion_protection"), True)
    expect("aws_db_instance.manage_master_user_password", db.get("manage_master_user_password"), True)
    expect("aws_db_instance.publicly_accessible", db.get("publicly_accessible"), False)
    expect("aws_db_instance.skip_final_snapshot", db.get("skip_final_snapshot"), False)
    retention = db.get("backup_retention_period")
    expect("aws_db_instance.backup_retention_period >= 7", isinstance(retention, int) and retention >= 7, True)

    pg = (by_type.get("aws_db_parameter_group") or [{}])[0].get("values", {})
    expect("aws_db_parameter_group.family", pg.get("family"), "postgres" + args.engine_version.split(".")[0])
    params = {p["name"]: p["value"] for p in pg.get("parameter") or []}
    for name, value in EXPECTED_PARAMETERS.items():
        expect(f"aws_db_parameter_group.parameter[{name}]", params.get(name), value)

    rules = by_type.get("aws_vpc_security_group_ingress_rule", [])
    cidrs = sorted(r["values"].get("cidr_ipv4") for r in rules)
    expect("ingress cidr_ipv4", cidrs, sorted(args.allowed_cidr))
    ports = sorted({(r["values"].get("from_port"), r["values"].get("to_port"), r["values"].get("ip_protocol")) for r in rules})
    expect("ingress ports", ports, [(5432, 5432, "tcp")])
    sg = (by_type.get("aws_security_group") or [{}])[0].get("values", {})
    # Inline rules are computed (null) at plan time; any planned inline rule fails.
    expect("aws_security_group inline ingress/egress rules", [sg.get("ingress") or [], sg.get("egress") or []], [[], []])

    print(f"{'address':60} {'run_token':28} Expires")
    for address, token, expires in tag_rows:
        print(f"{address:60} {str(token):28} {expires}")
    print(f"Checked tags on {len(tag_rows)} managed resources.\n")
    print(f"{'setting':55} {'planned':28} result")
    for label, actual, result in settings:
        print(f"{label:55} {json.dumps(actual):28} {result}")

    if failures:
        print("\nbilling-db plan check failed:", file=sys.stderr)
        for f in failures:
            print(f"- {f}", file=sys.stderr)
        return 1
    print("\nbilling-db plan check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
