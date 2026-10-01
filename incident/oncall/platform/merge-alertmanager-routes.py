#!/usr/bin/env python3
"""Merge on-call routes while keeping configuration and command output private."""

import argparse
import base64
import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

ONCALL_RECEIVERS = {"oncall-devin", "oncall-channel"}
ROUTES_FILE = Path(__file__).with_name("alertmanager-routes.yaml")


def mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(k, str) for k in value):
        raise ValueError("Expected a mapping")
    return dict(value)


def sequence(value: object) -> list[object]:
    if not isinstance(value, list):
        raise ValueError("Expected a list")
    return list(value)


def merge_config(config: dict[str, object], url: str, secret: str) -> dict[str, object]:
    if bool(url) != bool(secret):
        raise ValueError("Set both on-call webhook environment variables")
    merged = copy.deepcopy(config)
    root = mapping(merged["route"])
    existing_routes = [
        r
        for r in sequence(root.get("routes", []))
        if mapping(r).get("receiver") not in ONCALL_RECEIVERS
    ]
    receivers = [
        r
        for r in sequence(merged.get("receivers", []))
        if mapping(r).get("name") not in ONCALL_RECEIVERS
    ]
    template = mapping(yaml.safe_load(ROUTES_FILE.read_text()))
    routes = [
        r for r in sequence(template["routes"]) if url or mapping(r)["receiver"] != "oncall-devin"
    ]
    for item in sequence(template["receivers"]):
        receiver = mapping(item)
        if receiver["name"] == "oncall-devin":
            if not url:
                continue
            webhook = mapping(sequence(receiver["webhook_configs"])[0])
            webhook["url"] = url
            webhook["http_config"] = {"http_headers": {"X-Webhook-Secret": {"values": [secret]}}}
            receiver["webhook_configs"] = [webhook]
        receivers.append(receiver)
    root["routes"] = routes + existing_routes
    merged["route"] = root
    merged["receivers"] = receivers
    return merged


def run_private(command: list[str], payload: str | None = None) -> str:
    result = subprocess.run(command, input=payload, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError("Private command failed")
    return result.stdout


def validate_config(rendered: str) -> None:
    run_private(
        [
            "docker",
            "run",
            "--rm",
            "-i",
            "--network=none",
            "--read-only",
            "--tmpfs",
            "/work:rw,mode=1777",
            "--entrypoint",
            "/bin/sh",
            os.environ.get("ONCALL_AMTOOL_IMAGE", "prom/alertmanager:v0.34.1"),
            "-c",
            "umask 077; cat > /work/config.yml; amtool check-config /work/config.yml",
        ],
        rendered,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="Synthetic config for an offline check")
    parser.add_argument("--output", type=Path, help="Write the merged synthetic config")
    parser.add_argument(
        "--apply", action="store_true", help="Patch the live Secret after validation"
    )
    args = parser.parse_args()
    if (args.output and not args.config) or (args.config and args.apply):
        parser.error("--output requires --config; --config cannot be applied")
    url = os.environ.get("ONCALL_DEVIN_WEBHOOK_URL", "")
    webhook_secret = os.environ.get("ONCALL_DEVIN_WEBHOOK_SECRET", "")
    if bool(url) != bool(webhook_secret):
        raise ValueError("Set both webhook variables")
    kubectl = ["kubectl", "-n", "monitoring"]
    resource_version = ""
    if args.config:
        raw = args.config.read_text()
    else:
        live = mapping(
            json.loads(
                run_private(kubectl + ["get", "secret", "alertmanager-config", "-o", "json"])
            )
        )
        data = mapping(live["data"])
        encoded = data["alertmanager.yaml"]
        if not isinstance(encoded, str):
            raise ValueError("Invalid Secret data")
        raw = base64.b64decode(encoded, validate=True).decode()
        resource_version = mapping(live["metadata"])["resourceVersion"]
    merged = merge_config(mapping(yaml.safe_load(raw)), url, webhook_secret)
    rendered = yaml.safe_dump(merged, sort_keys=False)
    validate_config(rendered)
    if args.output:
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as output:
            output.write(rendered)
    if args.apply and rendered != raw:
        patch = [
            {"op": "test", "path": "/metadata/resourceVersion", "value": resource_version},
            {
                "op": "replace",
                "path": "/data/alertmanager.yaml",
                "value": base64.b64encode(rendered.encode()).decode(),
            },
        ]
        run_private(
            kubectl
            + ["patch", "secret", "alertmanager-config", "--type=json", "--patch-file=/dev/stdin"],
            json.dumps(patch),
        )
    names = [mapping(r)["receiver"] for r in sequence(mapping(merged["route"])["routes"])]
    print("Route receivers: " + ", ".join(str(name) for name in names))
    print("Receivers: " + ", ".join(str(mapping(r)["name"]) for r in sequence(merged["receivers"])))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, yaml.YAMLError):
        print(
            "Alertmanager merge failed; configuration and command output suppressed.",
            file=sys.stderr,
        )
        sys.exit(1)
