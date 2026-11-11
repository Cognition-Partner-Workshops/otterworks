from __future__ import annotations

import subprocess
import time
from collections import Counter, defaultdict

from .transports import env_value

TESTS = ("broker-kill", "consumer-restart", "poison", "ordering")


def docker(action: str, container: str):
    if not container or container.startswith("-"):
        raise ValueError("An explicit container name is required")
    subprocess.run(["docker", action, container], check=True, capture_output=True, timeout=60)


class FaultHook:
    def __init__(self, test, spec, broker, count, control=docker, sleep=time.sleep):
        self.test, self.spec, self.broker = test, dict(spec), broker
        if test in ("broker-kill", "consumer-restart"):
            self.spec["container"] = env_value(spec, "container")
        self.control, self.sleep = control, sleep
        self.events = []
        self.stopped = False
        if test in ("broker-kill", "consumer-restart"):
            if not 0 < spec["after_message"] < count:
                raise ValueError("Fault must interrupt a non-empty replay before the last message")
            if test == "consumer-restart" and not spec["after_message"] < spec["restart_after"] <= count:
                raise ValueError("Consumer restart must follow offline publishing")

    def after_message(self, count):
        if self.test not in ("broker-kill", "consumer-restart"):
            return
        spec = self.spec
        if count == spec["after_message"]:
            action = "kill" if self.test == "broker-kill" else "stop"
            self.control(action, spec["container"])
            self.stopped = True
            self.events.append({"action": action, "published": count})
            if self.test == "broker-kill":
                self.sleep(float(spec.get("downtime", 1)))
                self.restore(count)
                deadline = time.monotonic() + float(spec.get("ready_timeout", 30))
                while True:
                    try:
                        self.broker.reconnect()
                        break
                    except Exception:
                        if time.monotonic() >= deadline:
                            raise
                        self.sleep(0.25)
        if self.test == "consumer-restart" and count == spec["restart_after"]:
            self.restore(count)

    def restore(self, count=None):
        if self.stopped:
            self.control("start", self.spec["container"])
            self.stopped = False
            self.events.append({"action": "start", "published": count})


def field(message, name):
    return message["headers"][name]


def fault_result(test: str, spec: dict, expected: list, actual: list, events: list) -> dict:
    reasons = []
    evidence = {"events": events}
    try:
        if test in ("broker-kill", "consumer-restart"):
            identity = spec["identity_header"]
            wanted = Counter(field(m, identity) for m in expected)
            seen = Counter(field(m, identity) for m in actual)
            if not wanted or any(count != 1 for count in wanted.values()):
                reasons.append("Expected message identities must be non-empty and unique")
            if wanted != seen:
                reasons.append("Messages lost, duplicated or unexpected")
            required = "kill" if test == "broker-kill" else "stop"
            if [e["action"] for e in events] != [required, "start"]:
                reasons.append("Fault lifecycle did not execute")
            if test == "consumer-restart":
                if not spec.get("topic") or not spec.get("durable_subscription"):
                    reasons.append("Durable topic and subscription must be declared")
                if not spec["published"] or not all(m["destination"] == spec.get("topic") for m in spec["published"]):
                    reasons.append("Offline messages were not published to the declared topic")
            evidence.update(expected_ids=dict(wanted), actual_ids=dict(seen))
        elif test == "poison":
            if spec["redeliveries"] < 0 or spec["audit_destination"] == spec["dlq"]:
                raise ValueError("Poison test requires non-negative retries and separate audit and DLQ destinations")
            identity = spec["identity_header"]
            poison = spec["identity"]
            attempts = [m for m in actual if m["destination"] == spec["audit_destination"]
                        and field(m, identity) == poison]
            counts = [int(field(m, spec["delivery_count_header"])) for m in attempts]
            dlq = [m for m in actual if m["destination"] == spec["dlq"]
                   and field(m, identity) == poison]
            if counts != list(range(1, spec["redeliveries"] + 2)):
                reasons.append("Redelivery attempts differ")
            if len(dlq) != 1:
                reasons.append("Expected exactly one poison message on declared DLQ")
            evidence.update(delivery_counts=counts, dlq=spec["dlq"], dlq_count=len(dlq))
        elif test == "ordering":
            def sequences(messages):
                groups = defaultdict(list)
                for message in messages:
                    groups[field(message, spec["key_header"])].append(field(message, spec["sequence_header"]))
                return dict(groups)
            wanted, seen = sequences(expected), sequences(actual)
            if any(len(values) != len(set(values)) for values in wanted.values()):
                reasons.append("Expected sequence positions must be unique per key")
            if not wanted or wanted != seen:
                reasons.append("Per-key ordering or membership differs")
            if spec.get("parallel_consumers", 0) < 2:
                reasons.append("Declare at least two parallel consumers in the tested deployment")
            evidence.update(expected_sequences=wanted, actual_sequences=seen,
                            declared_parallel_consumers=spec.get("parallel_consumers"))
        else:
            raise ValueError("Unknown fault test")
    except (KeyError, TypeError, ValueError) as exc:
        reasons.append(f"Incomplete fault evidence: {exc}")
    return {"test": test, "status": "failed" if reasons else "passed", "reasons": reasons,
            "evidence": evidence}
