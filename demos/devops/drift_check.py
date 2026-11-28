import argparse
import json
from pathlib import Path
import subprocess
import sys

import yaml

DEMO = Path(__file__).resolve().parent
ROOT = DEMO.parents[1]
sys.path.insert(0, str(ROOT / "platform" / "standards" / "fleet"))
import fleet

CHART = ROOT / "platform" / "standards" / "helm" / "app"
NAMESPACE = "devops-fleet"
WORKLOADS = ("api-gateway", "auth-service", "collab-service", "document-service",
             "file-service", "search-service")
SNAPSHOT = DEMO / "fixtures" / "observed-deployments.json"


def render_deployments():
    for workload in WORKLOADS:
        render = subprocess.run(
            ["helm", "template", workload, str(CHART), "--namespace", NAMESPACE,
             "-f", str(DEMO / "values" / "common.yaml"),
             "-f", str(DEMO / "values" / f"{workload}.yaml"),
             "--show-only", "templates/deployment.yaml"],
            capture_output=True, check=True, text=True, encoding="utf-8", timeout=30,
        )
        yield from (doc for doc in yaml.safe_load_all(render.stdout) if doc is not None)


def fields(deployment):
    spec = deployment["spec"]
    pod = spec["template"]
    result = {"/spec/replicas": spec.get("replicas", 1)}
    for prefix, metadata in (("/metadata", deployment["metadata"]),
                             ("/spec/template/metadata", pod.get("metadata", {}))):
        owner = metadata.get("labels", {}).get("owner")
        if owner is not None:
            result[f"{prefix}/labels/owner"] = owner
    for container in pod["spec"]["containers"]:
        prefix = f"/spec/template/spec/containers/{container['name']}"
        result[f"{prefix}/image"] = container["image"]
        for field in ("requests", "limits"):
            result[f"{prefix}/resources/{field}"] = container.get("resources", {}).get(field, {})
    return result


def compare(desired, observed):
    wanted = fleet.index(desired, NAMESPACE)
    actual = fleet.index(observed, NAMESPACE)
    changes = []
    for resource in sorted(wanted.keys() | actual.keys()):
        if resource not in wanted or resource not in actual:
            state = "missing resource" if resource in wanted else "unexpected resource"
            changes.append(dict(resource=resource, field="/", state=state,
                                desired=resource in wanted, observed=resource in actual))
            continue
        expected = fields(wanted[resource])
        current = fields(actual[resource])
        for field in sorted(expected.keys() | current.keys()):
            if expected.get(field) != current.get(field):
                state = ("missing" if field not in current else
                         "unexpected" if field not in expected else "changed")
                changes.append(dict(resource=resource, field=field, state=state,
                                    desired=expected.get(field), observed=current.get(field)))
    return {"resources_checked": len(wanted), "changes": changes}


def main():
    cli = argparse.ArgumentParser(description="Read-only drift check against the recorded kind fleet")
    cli.add_argument("--markdown", type=Path)
    cli.add_argument("--json", type=Path)
    args = cli.parse_args()
    try:
        snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        data = compare(render_deployments(), snapshot["items"])
        data["observed"] = {"source": snapshot["source"], "label": snapshot["fixture"]}
        data["result"] = "RED" if data["changes"] else "MATCH"
        columns = ("resource", "field", "state", "desired", "observed")
        heading = "Fleet drift — recorded kind Deployments"
        summary = (f"Observed: `{snapshot['source']}` ({snapshot['fixture']}).\n\n"
                   f"Result: **{data['result']}** — {data['resources_checked']} deployments checked, "
                   f"{len(data['changes'])} differences.\n")
        report = fleet.table(heading, columns, ([row[f] for f in columns] for row in data["changes"]))
        title, _, body = report.partition("\n\n")
        fleet.output(args.markdown, f"{title}\n\n{summary}\n{body}")
        if args.json:
            fleet.output(args.json, json.dumps(data, indent=2) + "\n")
        return int(bool(data["changes"]))
    except (OSError, KeyError, ValueError, yaml.YAMLError, subprocess.SubprocessError) as err:
        cli.exit(2, f"{getattr(err, 'stderr', None) or err}\n")


if __name__ == "__main__":
    raise SystemExit(main())
