import argparse
import json
import subprocess
from pathlib import Path

FIXTURE = "fixture: recorded, not live AWS"


def capture(context, namespace):
    if not context.startswith("kind-devops-20261128-"):
        raise ValueError("provide the run's local kind context")
    output = subprocess.check_output(
        ["kubectl", "--context", context, "-n", namespace, "get", "deployments", "-o", "json"],
        text=True, encoding="utf-8", timeout=30,
    )
    data = json.loads(output)
    for item in data["items"]:
        meta = item["metadata"]
        item["metadata"] = {key: meta[key] for key in ("name", "namespace", "labels")}
        spec = item["spec"]
        pod = spec["template"]
        pod_spec = pod["spec"]
        for container in pod_spec["containers"]:
            for field in ("terminationMessagePath", "terminationMessagePolicy"):
                container.pop(field, None)
        replicasets = ["kubectl", "--context", context, "-n", namespace, "get", "rs",
                       "-l", f"app={meta['name']}", "-o", "json"]
        rs_items = json.loads(subprocess.check_output(
            replicasets, text=True, encoding="utf-8", timeout=30))["items"]
        revisions = [
            {"revision": int(rs["metadata"]["annotations"]["deployment.kubernetes.io/revision"]),
             "replicas": rs["status"].get("replicas", 0),
             "ready_replicas": rs["status"].get("readyReplicas", 0)}
            for rs in rs_items
        ]
        item["rollout_revisions"] = sorted(revisions, key=lambda row: row["revision"])
        history = json.loads(subprocess.check_output(
            ["helm", "--kube-context", context, "-n", namespace,
             "history", meta["name"], "-o", "json"], text=True, encoding="utf-8", timeout=30))
        item["helm_history"] = [
            {key: row[key] for key in ("revision", "status", "description")} for row in history
        ]
        item["status"] = {key: item["status"].get(key, 0) for key in
                          ("replicas", "readyReplicas", "updatedReplicas", "availableReplicas")}
    return {"fixture": FIXTURE, "source": context, "kind": "List", "items": data["items"]}


def main():
    cli = argparse.ArgumentParser(description="Record the local fleet's Deployment objects")
    cli.add_argument("--context", required=True)
    cli.add_argument("--namespace", default="devops-fleet")
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    args.output.write_text(json.dumps(capture(args.context, args.namespace), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
