"""Live broker-kill proof against a transactional echo, not a migrated flow."""

import json
import os
from pathlib import Path

import yaml

from integration.harness.fingerprints import record_lock


def create(root=Path("/state/fault-corpus")):
    root.mkdir(parents=True, exist_ok=True)
    config = yaml.safe_load(Path("integration/corpus/destinations.yaml").read_text())
    config["ignore"].append("/messages/*/headers/transaction")
    (root / "destinations.yaml").write_text(yaml.safe_dump(config))
    inputs = [{"destination": "REPLAY.SMOKE.IN", "body": f"echo-{n}",
               "properties": {"requestId": f"echo-{n}"}} for n in range(5)]
    expected = [{"destination": "REPLAY.SMOKE.OUT", "body": m["body"], "headers": m["properties"]} for m in inputs]
    flow = {"inputs": {"messages": inputs}, "capture_seconds": 5, "publish_interval": 0.5,
            "capture": {"messages": [{"id": "echo-proof", "destination": "REPLAY.SMOKE.OUT"}]},
            "expected": {"messages": expected, "db": {}, "files": {}},
            "faults": {"broker-kill": {"container": os.environ["REPLAY_BROKER_CONTAINER"],
                                         "after_message": 2, "ready_timeout": 60, "identity_header": "requestId"}}}
    (root / "echo").mkdir(exist_ok=True)
    (root / "echo/flow.json").write_text(json.dumps(flow, indent=2) + "\n")
    record_lock(root, "isolated transactional echo broker-kill smoke")
    print("Created locked live-fault corpus")


if __name__ == "__main__":
    create()
