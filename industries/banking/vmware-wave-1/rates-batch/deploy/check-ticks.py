#!/usr/bin/env python3
"""Check embedded ticks; regenerate with kubectl create configmap rates-ticks
--from-file=../../data/rates/in --dry-run=client -o yaml > kind-deps/ticks.yaml
(run from this directory).
"""
from pathlib import Path
import yaml

deploy = Path(__file__).resolve().parent
embedded = yaml.safe_load((deploy / "kind-deps/ticks.yaml").read_text())["data"]
source = deploy.parent.parent / "data/rates/in"
assert set(embedded) == {p.name for p in source.glob("*.csv")}
for name, content in embedded.items():
    assert content.encode("utf-8") == (source / name).read_bytes(), name
print("ticks ConfigMap: all three files byte-identical")
