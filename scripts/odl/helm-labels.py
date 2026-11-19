#!/usr/bin/env python3
import sys

import yaml

for obj in yaml.safe_load_all(sys.stdin):
    if not obj:
        continue
    obj.setdefault("metadata", {}).setdefault("labels", {})["run_token"] = "odl-1795112287"
    if obj["kind"] in ("Deployment", "StatefulSet", "DaemonSet", "Job"):
        obj["spec"]["template"].setdefault("metadata", {}).setdefault("labels", {})["run_token"] = "odl-1795112287"
    print("---")
    print(yaml.safe_dump(obj, sort_keys=False))
