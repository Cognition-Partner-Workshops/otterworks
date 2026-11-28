import argparse
import http.client
import json
import math
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import time
from urllib.parse import urlsplit

from fleet import kubectl, output, table


def validate(profile):
    for key, low, high in (
        ("requests", 1, 3000), ("rate_per_second", 1, 50), ("concurrency", 1, 16),
        ("timeout_seconds", 1, 10), ("sample_seconds", 1, 10),
    ):
        value = profile[key]
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f"{key} must be an integer between {low} and {high}")
    if not 0 < profile["p95_limit_ms"] or not 0 <= profile["allowed_failures"] <= profile["requests"]:
        raise ValueError("invalid acceptance thresholds")


def target(url):
    value = urlsplit(url)
    if (value.scheme != "http" or value.hostname not in {"127.0.0.1", "::1"}
            or value.port is None or value.username or value.password or value.fragment):
        raise ValueError("use a loopback HTTP URL from kubectl port-forward")
    return value


def request(url, timeout):
    connection = http.client.HTTPConnection(url.hostname, url.port, timeout=timeout)
    start = time.monotonic()
    try:
        path = url.path or "/"
        connection.request("GET", f"{path}?{url.query}" if url.query else path)
        response = connection.getresponse()
        return response.status, round((time.monotonic() - start) * 1000, 3)
    except (OSError, http.client.HTTPException):
        return None, round((time.monotonic() - start) * 1000, 3)
    finally:
        connection.close()


def emit_load(url, profile):
    with ThreadPoolExecutor(max_workers=profile["concurrency"]) as pool:
        futures = []
        start = time.monotonic()
        for i in range(profile["requests"]):
            time.sleep(max(0, start + i / profile["rate_per_second"] - time.monotonic()))
            futures.append(pool.submit(request, url, profile["timeout_seconds"]))
        return [future.result() for future in futures]


def snapshot(context, namespace, deployment):
    def get(*args):
        return json.loads(kubectl(context, namespace, *args))

    workload = get("get", "deployment", deployment, "-o", "json")
    selector = workload["spec"]["selector"]
    terms = [f"{key}={val}" for key, val in selector.get("matchLabels", {}).items()]
    for rule in selector.get("matchExpressions", []):
        key, op = rule["key"], rule["operator"]
        if op in ("In", "NotIn"):
            terms.append(f"{key} {'in' if op == 'In' else 'notin'} ({','.join(rule['values'])})")
        else:
            terms.append(key if op == "Exists" else "!" + key)
    if not terms:
        raise ValueError("deployment has an empty selector")
    replicasets = get("get", "rs", "-l", ",".join(terms), "-o", "json")["items"]

    def owned_by(resource, uids):
        return any(ref["uid"] in uids and ref.get("controller")
                   for ref in resource["metadata"].get("ownerReferences", []))

    rs_ids = {rs["metadata"]["uid"] for rs in replicasets
              if owned_by(rs, {workload["metadata"]["uid"]})}
    pods = [pod for pod in get("get", "pods", "-l", ",".join(terms), "-o", "json")["items"]
            if owned_by(pod, rs_ids)]
    restarts = {pod["metadata"]["uid"]: sum(x["restartCount"] for x in
                pod.get("status", {}).get("containerStatuses", [])) for pod in pods}
    usages = {uid: None for uid in restarts}
    nodes = {pod["spec"]["nodeName"] for pod in pods if "nodeName" in pod["spec"]}
    for node in nodes:
        metrics = get("get", "--raw", f"/api/v1/nodes/{node}/proxy/stats/summary")
        for row in metrics["pods"]:
            uid = row["podRef"]["uid"]
            if uid in usages:
                usages[uid] = row.get("cpu", {}).get("usageNanoCores")
    status = workload.get("status", {})
    return {
        "cpu_millicores": round(sum(usages.values()) / 1_000_000, 3)
        if usages and all(value is not None for value in usages.values()) else None,
        "pods": restarts,
        "replicas": status.get("replicas", 0),
        "ready_replicas": status.get("readyReplicas", 0),
    }


def measure(profile, url, sample):
    start = time.monotonic()
    initial = sample()
    samples = []
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(emit_load, url, profile)
        while not future.done():
            samples.append(sample())
            time.sleep(profile["sample_seconds"])
        results = future.result()
    final = sample()
    samples = samples or [final]
    cpu = [row["cpu_millicores"] for row in [*samples, final] if row["cpu_millicores"] is not None]
    times = sorted(duration for status, duration in results if status is not None and 200 <= status < 300)
    failures = len(results) - len(times)
    p95 = times[math.ceil(0.95 * len(times)) - 1] if times else None
    return {
        "profile": profile, "endpoint": (url.path or "/") + ("?" + url.query if url.query else ""),
        "requests": len(results), "failures": failures, "p95_ms": p95,
        "cpu_peak_millicores": max(cpu) if cpu else None,
        "restarts_before": sum(initial["pods"].values()), "restarts_after": sum(final["pods"].values()),
        "restarts_on_retained_pods": sum(value - initial["pods"][uid]
                                        for uid, value in final["pods"].items() if uid in initial["pods"]),
        "replaced_or_removed_pods": len(initial["pods"].keys() - final["pods"].keys()),
        "replicas_before": initial["replicas"], "replicas_after": final["replicas"],
        "ready_replicas_after": final["ready_replicas"],
        "replicas_peak": max(row["replicas"] for row in [initial, *samples, final]),
        "elapsed_seconds": round(time.monotonic() - start, 3),
        "passed": bool(cpu and p95 is not None and p95 <= profile["p95_limit_ms"]
                       and failures <= profile["allowed_failures"]),
    }


def compare(before, after):
    for key in ("profile", "endpoint", "deployment"):
        if before.get(key) != after.get(key):
            raise ValueError(f"before and after must use the same {key}")
    return {"before": before, "after": after}


def render(report):
    fields = ("requests", "failures", "p95_ms", "cpu_peak_millicores", "restarts_before",
              "restarts_after", "restarts_on_retained_pods", "replaced_or_removed_pods",
              "replicas_before", "replicas_after", "replicas_peak", "ready_replicas_after",
              "elapsed_seconds", "passed")
    phases = list(report)
    return table("Bounded load", ["Metric", *phases],
                 ([field, *(report[phase][field] for phase in phases)] for field in fields))


def main():
    cli = argparse.ArgumentParser(description="Compare fixed loopback load against a kind deployment")
    commands = cli.add_subparsers(dest="command", required=True)
    capture = commands.add_parser("capture")
    for name in ("profile", "deployment", "context", "namespace", "url"):
        capture.add_argument(f"--{name}", required=True)
    comparison = commands.add_parser("compare")
    for phase in ("before", "after"):
        comparison.add_argument(phase)
    for command in (capture, comparison):
        command.add_argument("--json", required=True)
        command.add_argument("--markdown")
    args = cli.parse_args()
    try:
        def read(path):
            return json.loads(Path(path).read_text(encoding="utf-8"))

        if args.command == "capture":
            if not args.context.startswith("kind-"):
                raise ValueError("capture requires an explicit kind context")
            profile = read(args.profile)
            validate(profile)
            row = measure(profile, target(args.url),
                          lambda: snapshot(args.context, args.namespace, args.deployment))
            row["deployment"] = args.deployment
            report = {"measurement": row}
            data = row
        else:
            report = compare(read(args.before), read(args.after))
            row = report["after"]
            data = report
        output(args.json, json.dumps(data, indent=2) + "\n")
        output(args.markdown, render(report))
        return 0 if row["passed"] else 1
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as err:
        cli.exit(2, f"{getattr(err, 'stderr', None) or err}\n")


if __name__ == "__main__":
    raise SystemExit(main())
