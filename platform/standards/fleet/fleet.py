import argparse
import json
import subprocess
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent


def documents(path):
    for doc in yaml.safe_load_all(Path(path).read_text(encoding="utf-8")):
        if doc is None:
            continue
        if doc.get("kind") == "List":
            yield from doc["items"]
        else:
            yield doc


def identity(doc, namespace):
    meta = doc["metadata"]
    group = doc["apiVersion"].partition("/")[0] if "/" in doc["apiVersion"] else "core"
    return "/".join((group, doc["kind"], meta.get("namespace", namespace), meta["name"]))


def index(docs, namespace):
    by_id = {}
    for doc in docs:
        key = identity(doc, namespace)
        if key in by_id:
            raise ValueError(f"duplicate resource: {key}")
        by_id[key] = doc
    return by_id


def kubectl(context, namespace, *args, data=None):
    return subprocess.run(
        ["kubectl", "--context", context, "--namespace", namespace, *args],
        input=data, text=True, encoding="utf-8", capture_output=True, check=True, timeout=45,
    ).stdout


def live_objects(context, namespace, desired):
    manifest = yaml.safe_dump_all(desired)
    response = kubectl(context, namespace, "get", "-f", "-", "-o", "json",
                       "--ignore-not-found", data=manifest)
    if not response.strip():
        return []
    result = json.loads(response)
    return result["items"] if result["kind"] == "List" else [result]


def changes(expected, observed, path=""):
    if isinstance(expected, dict) and isinstance(observed, dict):
        for key, value in expected.items():
            field = f"{path}/{str(key).replace('~', '~0').replace('/', '~1')}"
            if key not in observed:
                yield {"field": field, "state": "missing", "desired": value, "observed": None}
            else:
                yield from changes(value, observed[key], field)
    elif isinstance(expected, list) and isinstance(observed, list):
        if all(isinstance(item, dict) and "name" in item for item in expected + observed):
            wanted = {item["name"]: item for item in expected}
            actual = {item["name"]: item for item in observed}
            for name in sorted(wanted.keys() | actual.keys()):
                field = f"{path}/{name}"
                if name not in wanted or name not in actual:
                    yield {"field": field, "state": "unexpected" if name in actual else "missing",
                           "desired": wanted.get(name), "observed": actual.get(name)}
                else:
                    yield from changes(wanted[name], actual[name], field)
        elif expected != observed:
            yield {"field": path, "state": "changed", "desired": expected, "observed": observed}
    elif expected != observed:
        yield {"field": path, "state": "changed", "desired": expected, "observed": observed}


def drift(desired, observed, namespace):
    wanted = index(desired, namespace)
    actual = index(observed, namespace)
    rows = []
    for key in sorted(wanted.keys() | actual.keys()):
        if key not in wanted or key not in actual:
            rows.append({"resource": key, "field": "/", "state":
                         "unexpected resource" if key in actual else "missing resource",
                         "desired": key in wanted, "observed": key in actual})
            continue
        for field in ("spec", "data", "binaryData", "rules"):
            if field in wanted[key]:
                rows.extend({"resource": key, **change} for change in changes(
                    wanted[key][field], actual[key].get(field), f"/{field}"))
        for field in ("labels", "annotations"):
            rows.extend({"resource": key, **change} for change in changes(
                wanted[key]["metadata"].get(field, {}),
                actual[key]["metadata"].get(field, {}), f"/metadata/{field}"))
    return {"resources_checked": len(wanted), "changes": rows}


def api_compat(docs, target, catalog, namespace):
    if target not in catalog["targets"]:
        raise ValueError(f"unsupported target: {target}")
    minor = int(target.split(".")[1])
    counts = dict(removed=0, deprecated=0, no_catalog_finding=0)
    rows = []
    for key, doc in sorted(index(docs, namespace).items()):
        rules = [rule for rule in catalog["rules"] if rule["apiVersion"] == doc["apiVersion"]
                 and ("kinds" not in rule or doc["kind"] in rule["kinds"])]
        row = {"resource": key, "apiVersion": doc["apiVersion"], "status": "no_catalog_finding"}
        for rule in rules:
            if rule.get("removed_minor", 999) <= minor:
                row["status"] = "removed"
            elif rule.get("deprecated_minor", 999) <= minor:
                row["status"] = "deprecated"
            else:
                continue
            row.update(replacement=rule["replacement"], removed_minor=rule.get("removed_minor"))
            break
        counts[row["status"]] += 1
        rows.append(row)
    return {"target": target, "counts": counts, "resources": rows}


def cell(value):
    if value is None or value == "":
        return "unknown"
    if isinstance(value, (dict, list, bool)):
        value = json.dumps(value, sort_keys=True, ensure_ascii=False)
    return (str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace("|", "&#124;").replace("\r", "").replace("\n", "<br>"))


def table(title, fields, rows):
    def line(values):
        return "| " + " | ".join(cell(value) for value in values) + " |"

    return "\n".join([f"# {title}", "", line(fields), line(["---"] * len(fields)),
                      *(line(row) for row in rows), ""])


BOARD_FIELDS = (
    ("workload", "Workload"), ("owner", "Owner"), ("deployed_revision", "Deployed revision"),
    ("desired_revision", "Desired revision"), ("api_status", "API status"),
    ("addon_status", "Add-on status"), ("hpa", "HPA"), ("requests", "Requests"),
    ("proof", "Proof"), ("rollback", "Rollback"), ("status", "Readiness"),
)


def board(inventory):
    workloads = sorted(inventory["workloads"], key=lambda row: row["workload"])
    counts = dict(ready=0, held=0, rejected=0)
    seen = set()
    for row in workloads:
        if row["workload"] in seen:
            raise ValueError(f"duplicate board workload: {row['workload']}")
        seen.add(row["workload"])
        if row["status"] not in counts:
            raise ValueError(f"invalid readiness: {row['status']}")
        if row["status"] == "ready" and any(not row.get(key) for key, _ in BOARD_FIELDS):
            raise ValueError(f"ready workload needs every board field: {row['workload']}")
        counts[row["status"]] += 1
    return table("Fleet readiness", [label for _, label in BOARD_FIELDS],
                 ([row.get(key) for key, _ in BOARD_FIELDS] for row in workloads)) + (
                     "\n" + ", ".join(f"{name}: {count}" for name, count in counts.items()) + "\n"
                 )


def output(path, content):
    if path:
        Path(path).write_text(content, encoding="utf-8")
    else:
        print(content, end="")


def parser():
    cli = argparse.ArgumentParser(description="Fleet readiness checks")
    sub = cli.add_subparsers(dest="check", required=True)
    drift_cli = sub.add_parser("drift")
    drift_cli.add_argument("desired")
    source = drift_cli.add_mutually_exclusive_group(required=True)
    source.add_argument("--observed")
    source.add_argument("--context")
    api_cli = sub.add_parser("api")
    api_cli.add_argument("manifests")
    api_cli.add_argument("--target", required=True)
    api_cli.add_argument("--catalog", type=Path, default=HERE / "api-catalog.json")
    board_cli = sub.add_parser("board")
    board_cli.add_argument("inventory")
    for command in (drift_cli, api_cli):
        command.add_argument("--namespace", default="default")
        command.add_argument("--json")
    for command in (drift_cli, api_cli, board_cli):
        command.add_argument("--markdown")
    return cli


def main():
    cli = parser()
    args = cli.parse_args()
    try:
        if args.check == "board":
            output(args.markdown, board(json.loads(Path(args.inventory).read_text(encoding="utf-8"))))
            return 0
        if args.check == "drift":
            desired = list(documents(args.desired))
            observed = (documents(args.observed) if args.observed
                        else live_objects(args.context, args.namespace, desired))
            data = drift(desired, observed, args.namespace)
            fields = ("resource", "field", "state", "desired", "observed")
            rows = data["changes"]
            red = bool(rows)
        else:
            catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
            data = api_compat(documents(args.manifests), args.target, catalog, args.namespace)
            data["catalog_source"] = catalog["source"]
            fields = ("resource", "apiVersion", "status", "replacement", "removed_minor")
            rows = data["resources"]
            red = bool(data["counts"]["removed"])
        output(args.markdown, table(args.check, fields, ([row.get(f) for f in fields] for row in rows)))
        if args.json:
            output(args.json, json.dumps(data, indent=2) + "\n")
        return int(red)
    except (OSError, KeyError, ValueError, yaml.YAMLError, subprocess.SubprocessError) as err:
        cli.exit(2, f"{getattr(err, 'stderr', None) or err}\n")


if __name__ == "__main__":
    raise SystemExit(main())
