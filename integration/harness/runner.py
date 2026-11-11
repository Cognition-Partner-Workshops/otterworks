from __future__ import annotations

import json
import time
from pathlib import Path

import yaml

from .diffing import differences
from .faults import FaultHook, fault_result
from .fingerprints import verify_lock
from .transports import Broker, Resources, safe_path


def load_corpus(root: Path, selected=()):
    lock = verify_lock(root)
    try:
        config = yaml.safe_load((root / "destinations.yaml").read_text())
    except yaml.YAMLError:
        raise ValueError("Invalid destination map") from None
    if not isinstance(config, dict):
        raise ValueError("Destination map must be an object")
    flows = sorted(p.parent.name for p in root.glob("*/flow.json"))
    if selected:
        if set(selected) - set(flows):
            raise ValueError("Unknown flow selection")
        flows = [name for name in flows if name in selected]
    if not flows:
        raise ValueError("Corpus contains no flows")
    return config, [(name, json.loads(safe_path(root, f"{name}/flow.json").read_text()))
                    for name in flows], lock


def replay_flow(name, flow, config, test=None, broker_factory=Broker, resource_factory=Resources,
                sleep=time.sleep, hook_factory=FaultHook):
    row = {"flow": name, "replayed": 0, "matched": 0, "differing": 0, "status": "error",
           "differences": [], "faults": []}
    broker = broker_factory(config.get("broker", {}), flow.get("capture", {}).get("messages", []))
    resources = resource_factory(config)
    hook = None
    try:
        messages = flow.get("inputs", {}).get("messages", [])
        expected = flow["expected"]
        spec = dict(flow["faults"][test]) if test else None
        if spec is not None:
            spec["published"] = messages[spec["after_message"]:spec["restart_after"]] if test == "consumer-restart" else []
            hook = hook_factory(test, spec, broker, len(messages))
        if messages or flow.get("capture", {}).get("messages"):
            broker.open()
        for message in messages:
            broker.send(message)
            row["replayed"] += 1
            if hook:
                hook.after_message(row["replayed"])
            sleep(float(flow.get("publish_interval", 0)))
        for item in flow.get("inputs", {}).get("files", []):
            resources.drop(item)
            row["replayed"] += 1
        sleep(float(flow.get("capture_seconds", 2)))
        capture = flow.get("capture", {})
        actual = {"messages": broker.snapshot(), "db": resources.database(capture.get("db", {})),
                  "files": resources.files(capture.get("files"))}
        ignore = config.get("ignore", []) + flow.get("ignore", [])
        compared_expected, compared_actual = expected, actual
        if test == "ordering":
            key = spec["key_header"]
            compared_expected = dict(expected, messages=sorted(expected["messages"], key=lambda m: m["headers"][key]))
            compared_actual = dict(actual, messages=sorted(actual["messages"], key=lambda m: m["headers"][key]))
        diffs = differences(compared_expected, compared_actual, ignore)
        row.update(actual=actual, differences=diffs)
        matched = sum(not differences(message, compared_actual["messages"][index], ignore,
                                      f"/messages/{index}")
                      for index, message in enumerate(compared_expected["messages"])
                      if index < len(compared_actual["messages"]))
        row["matched"] = matched
        row["differing"] = max(len(expected["messages"]), len(actual["messages"])) - matched
        if test:
            row["faults"].append(fault_result(test, spec, expected["messages"], actual["messages"], hook.events))
        row["status"] = "differing" if diffs or any(f["status"] != "passed" for f in row["faults"]) else "matched"
    except Exception as exc:
        # Driver errors can contain connection strings; record the type, not credentials.
        row["differences"].append({"path": "/", "reason": f"Replay error ({type(exc).__name__})"})
        if test:
            row["faults"].append({"test": test, "status": "failed", "reasons": ["Replay did not complete"],
                                  "evidence": {"events": hook.events if hook else []}})
    finally:
        try:
            if hook:
                hook.restore()
        except Exception as exc:
            row["status"] = "error"
            row["differences"].append({"path": "/", "reason": f"Fault cleanup error ({type(exc).__name__})"})
        try:
            broker.close()
        except Exception as exc:
            row["status"] = "error"
            row["differences"].append({"path": "/", "reason": f"Broker cleanup error ({type(exc).__name__})"})
    return row


def replay(root: Path, selected=(), test=None, **kwargs) -> dict:
    config, flows, lock = load_corpus(root, selected)
    return {"version": 1, "fixture": lock["files"],
            "flows": [replay_flow(name, flow, config, test, **kwargs) for name, flow in flows]}
