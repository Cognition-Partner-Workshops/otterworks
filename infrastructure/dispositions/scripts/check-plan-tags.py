#!/usr/bin/env python3
"""Verify mandatory run tags in a Terraform plan JSON document."""

import json
import sys


def resources(module):
    yield from module.get("resources", [])
    for child in module.get("child_modules", []):
        yield from resources(child)


def main():
    if len(sys.argv) != 4:
        raise SystemExit("usage: check-plan-tags.py PLAN.json RUN_TOKEN EXPIRES")

    plan_path, expected_token, expected_expires = sys.argv[1:]
    with open(plan_path, "rb") as plan_file:
        plan_bytes = plan_file.read()
    encoding = (
        "utf-16"
        if plan_bytes.startswith((b"\xff\xfe", b"\xfe\xff"))
        else "utf-8-sig"
    )
    plan = json.loads(plan_bytes.decode(encoding))

    root_module = plan.get("planned_values", {}).get("root_module")
    if not isinstance(root_module, dict):
        raise SystemExit("plan JSON has no planned_values.root_module")

    checked = []
    offenders = []
    for resource in resources(root_module):
        if resource.get("mode") != "managed":
            continue
        values = resource.get("values") or {}
        if "tags" not in values:
            continue
        tags = values.get("tags")
        address = resource.get("address", "<unknown-address>")
        checked.append((address, tags))
        if not isinstance(tags, dict):
            offenders.append(f"{address}: tags are null or not an object")
            continue
        if tags.get("run_token") != expected_token:
            offenders.append(
                f"{address}: run_token={tags.get('run_token')!r}, expected {expected_token!r}"
            )
        if tags.get("Expires") != expected_expires:
            offenders.append(
                f"{address}: Expires={tags.get('Expires')!r}, expected {expected_expires!r}"
            )

    if not checked:
        offenders.append("no managed resources with a planned tags field were checked")

    if offenders:
        print("Terraform plan tag check failed:", file=sys.stderr)
        for offender in offenders:
            print(f"- {offender}", file=sys.stderr)
        return 1

    print(f"{'address':72} {'run_token':24} Expires")
    print(f"{'-' * 72} {'-' * 24} {'-' * 20}")
    for address, tags in checked:
        print(f"{address:72} {tags['run_token']:24} {tags['Expires']}")
    print(f"Checked {len(checked)} managed resources with tags.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
