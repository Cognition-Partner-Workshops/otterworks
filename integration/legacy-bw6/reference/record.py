"""Freeze project XSLT/JVM results; transport expectations come from source configuration."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from integration.harness.fingerprints import record_lock

REFERENCE = Path(__file__).resolve().parent
LEGACY = REFERENCE.parent
ROOT = LEGACY.parents[1]


def source_hashes():
    return {str(p.relative_to(LEGACY)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(LEGACY.rglob("*")) if p.is_file() and "target" not in p.parts
            and "__pycache__" not in p.parts}


def record(corpus: Path, reason: str, settings: Path | None = None):
    if not reason.strip():
        raise ValueError("Reference recording requires a reason")
    command = ["mvn", "-B", "-f", str(REFERENCE / "pom.xml")]
    if settings:
        command.extend(["-s", str(settings)])
    subprocess.run(command + ["package", "dependency:build-classpath", "-Dmdep.outputFile=target/classpath.txt"], check=True)
    classpath = str(REFERENCE / "target/classes") + os.pathsep + (REFERENCE / "target/classpath.txt").read_text().strip()
    java = str(Path(os.environ["JAVA_HOME"]) / "bin/java")
    corpus.mkdir(parents=True, exist_ok=True)
    for spec in json.loads((REFERENCE / "cases.json").read_text()):
        output = REFERENCE / "target/captures" / spec["id"]
        output.mkdir(parents=True, exist_ok=True)
        command = [java, "-cp", classpath, "com.halvergate.reference.LegacyReference",
                   str(LEGACY / spec["stylesheet"]), spec["kind"]]
        for case in spec["cases"]:
            command.extend([str(REFERENCE / case["path"]), str(output / Path(case["path"]).name)])
        subprocess.run(command, check=True)
        inputs, expected, files = [], [], {}
        rows = {table: [] for table in spec["tables"]}
        for case in spec["cases"]:
            raw = (REFERENCE / case["path"]).read_text()
            request = ET.fromstring(raw)
            result = ET.parse(output / Path(case["path"]).name).getroot()
            inputs.append({"destination": spec["input"], "body": raw, "properties": case["properties"],
                           "headers": {"persistent": "true", "destination-type": "MULTICAST" if spec["domain"] == "account-events" and spec["kind"] != "durable" else "ANYCAST"}})
            if result.get("filtered"):
                continue
            headers = {key: case["properties"][key] for key in ("requestId", "accountId", "JMSXGroupID", "sequence")}
            body = result.findtext("body")
            if request.get("poison") == "true":
                resource = ET.parse(LEGACY / "SharedResources/EmsConnection.sharedresource").getroot()
                for count in range(1, int(resource.findtext("maxRedelivery")) + 2):
                    expected.append({"destination": "HB.DELIVERY.AUDIT", "body": body,
                                     "headers": {**headers, "deliveryCount": str(count)}})
                expected.append({"destination": resource.findtext("undeliveredQueue"), "body": raw, "headers": headers})
                continue
            expected.append({"destination": spec["output"], "body": body, "headers": headers})
            for table in spec["tables"]:
                rows[table].append({"flow": spec["id"], "request_id": result.get("id"),
                                    "account_id": result.get("account"), "currency": result.get("currency"),
                                    "amount": result.findtext("amount"), "status": result.findtext("status")})
            if spec["kind"] in ("date", "file", "file-service"):
                files[result.get("id") + ".txt"] = base64.b64encode(body.encode()).decode()
        captures = [{"id": "out", "destination": spec["output"],
                     "headers": {"subscription-type": "MULTICAST", "durable-subscription-name": "replay-account-evidence"}
                     if spec["kind"] == "durable" else {}}]
        if spec["kind"] == "poison":
            captures.extend([{"id": "attempts", "destination": "HB.DELIVERY.AUDIT"},
                             {"id": "dlq", "destination": "HB.UNDLV"}])
        capture = {"messages": captures, "db": {table: {
            "query": f"SELECT flow,request_id,account_id,amount,currency,status FROM {table} WHERE flow = %s ORDER BY request_id",
            "params": [spec["id"]]} for table in spec["tables"]}}
        if files:
            capture["files"] = {"transport": "sftp", "root": "/upload/out/" + spec["id"]}
        flow = {"inputs": {"messages": inputs, "files": []}, "capture": capture,
                "capture_seconds": 1, "publish_interval": 0.05,
                "expected": {"messages": expected, "db": rows, "files": files}, "faults": {}}
        if spec["kind"] == "date":
            flow["inputs"] = {"messages": [], "files": [{"path": m["properties"]["requestId"] + ".xml",
                                                          "base64": base64.b64encode(m["body"].encode()).decode()} for m in inputs]}
        if spec["kind"] == "xa":
            flow["faults"]["broker-kill"] = {"container_env": "REPLAY_BROKER_CONTAINER", "after_message": 1,
                                                "identity_header": "requestId", "ready_timeout": 45}
        if spec["kind"] == "durable":
            flow["faults"]["consumer-restart"] = {"container_env": "REPLAY_CONSUMER_CONTAINER", "after_message": 1,
                 "restart_after": 2, "identity_header": "requestId", "topic": spec["input"],
                 "durable_subscription": "records-event-fanout"}
            for message in flow["inputs"]["messages"]:
                message["headers"]["destination-type"] = "MULTICAST"
        if spec["kind"] == "ordering":
            flow["faults"]["ordering"] = {"key_header": "JMSXGroupID", "sequence_header": "sequence", "parallel_consumers": 2}
        if spec["kind"] == "poison":
            flow["faults"]["poison"] = {"identity_header": "requestId", "identity": "card-dispute-02", "audit_destination": "HB.DELIVERY.AUDIT",
                "delivery_count_header": "deliveryCount", "redeliveries": 3, "dlq": "HB.UNDLV"}
        directory = corpus / spec["id"]
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "flow.json").write_text(json.dumps(flow, indent=2) + "\n")
    (corpus / "source-hashes.json").write_text(json.dumps(source_hashes(), indent=2) + "\n")
    record_lock(corpus, reason)
    print("Recorded 24 flows using project stylesheets and JVM activities")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=ROOT / "integration/corpus")
    parser.add_argument("--reason", required=True)
    parser.add_argument("--maven-settings", type=Path)
    args = parser.parse_args()
    record(args.corpus, args.reason, args.maven_settings)
