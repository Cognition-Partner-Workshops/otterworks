#!/usr/bin/env python3
"""Add Tempo to the live trace pipeline, preserving every existing exporter."""

import argparse
import json
import subprocess
from pathlib import Path

import yaml


def add_tempo(config: dict) -> dict:
    exporters = config.setdefault("exporters", {})
    exporters["otlp_grpc/tempo"] = {
        "endpoint": "oncall-tempo.monitoring.svc.cluster.local:4317",
        "tls": {"insecure": True},
    }
    trace_exporters = config["service"]["pipelines"]["traces"]["exporters"]
    if "otlp_grpc/tempo" not in trace_exporters:
        trace_exporters.append("otlp_grpc/tempo")
    return config


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="Offline collector config")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if (args.output and not args.config) or (args.config and args.apply):
        parser.error("--output requires --config; --config cannot be applied")
    kubectl = ["kubectl", "-n", "monitoring"]
    if args.config:
        config = yaml.safe_load(args.config.read_text())
    else:
        live = json.loads(
            subprocess.check_output(kubectl + ["get", "configmap", "otel-collector", "-o", "json"])
        )
        config = yaml.safe_load(live["data"]["relay"])
    rendered = yaml.safe_dump(add_tempo(config), sort_keys=False)
    if args.output:
        args.output.write_text(rendered)
    if args.apply and rendered != live["data"]["relay"]:
        patch = [
            {
                "op": "test",
                "path": "/metadata/resourceVersion",
                "value": live["metadata"]["resourceVersion"],
            },
            {"op": "replace", "path": "/data/relay", "value": rendered},
        ]
        subprocess.run(
            kubectl
            + ["patch", "configmap", "otel-collector", "--type=json", "--patch-file=/dev/stdin"],
            input=json.dumps(patch),
            text=True,
            check=True,
        )
        subprocess.run(kubectl + ["rollout", "restart", "deployment/otel-collector"], check=True)
        subprocess.run(
            kubectl + ["rollout", "status", "deployment/otel-collector", "--timeout=180s"],
            check=True,
        )
    print("Trace exporter: otlp_grpc/tempo (existing exporters preserved)")


if __name__ == "__main__":
    main()
