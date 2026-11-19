#!/usr/bin/env python3
"""Safety checks for rendered charts (including CRDs skipped by kubeconform)."""

import sys

import yaml

objects = [obj for obj in yaml.safe_load_all(sys.stdin) if obj]
for obj in objects:
    kind = obj.get("kind")
    if kind == "Service" and obj.get("spec", {}).get("type") == "LoadBalancer":
        raise SystemExit("LoadBalancer Service is forbidden")
    if kind in ("ServiceMonitor", "PrometheusRule"):
        if obj.get("metadata", {}).get("labels", {}).get("release") != "prometheus":
            raise SystemExit(f"{kind} {obj['metadata']['name']} must have release: prometheus")
print(f"Manifest safety OK: {len(objects)} objects; no LoadBalancer; monitoring labels consistent")
