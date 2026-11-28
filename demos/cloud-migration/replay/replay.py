import argparse
import contextlib
import http.client
import json
import os
from pathlib import Path
import re
import selectors
import subprocess
import tempfile
import time


HERE = Path(__file__).resolve().parent
STANDARD = HERE.parents[2] / "platform/standards"
SAMPLE = STANDARD / "examples/sample-service"
CHART = STANDARD / "helm/app"
RUN_ID = "CMG_20261128"
APP = "sample-service"
SANDBOX = "cmg-20261128-sandbox"
REPOSITORY = "localhost/cmg-20261128/sample-service"
TAG = "baseline"
IMAGE = f"{REPOSITORY}:{TAG}"
NODE_IMAGE = "kindest/node:v1.32.2@sha256:f226345927d7e348497136874b6d207e0b32cc52154ad8323129352923a3142f"
CLUSTERS = {"aks-source": "simulated AKS source (kind)", "eks-target": "simulated EKS target (kind)"}
LIMITATION = "Local kind simulation only; this does not prove live AKS parity."
PRIVATE = {"id": "CMG-PRIVATE", "status": "unresolved", "execution": "not run"}
CHECKS = ("setup", "readiness", "restart", "sandbox_rollback")
VALUES = ("-f", SAMPLE / "deploy/values.yaml", "--set-string",
          f"image.repository={REPOSITORY},image.tag={TAG},image.pullPolicy=Never")


def command(*args, env=None, timeout=300):
    result = subprocess.run(args, env=env, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"Exit {result.returncode}: {subprocess.list2cmdline(args)}\n{result.stdout}")
    return result.stdout


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def identity(cluster):
    return {"cluster": cluster, "simulation": CLUSTERS[cluster],
            "context": f"kind-{cluster}", "namespace": SANDBOX}


def load_cases():
    cases = json.loads((HERE / "cases.json").read_text())
    require([case["id"] for case in cases] == [f"CMG-{i:02}" for i in range(1, 13)],
            "Expected stable case IDs CMG-01 through CMG-12")
    require(len({case["path"] for case in cases}) == len(cases), "Expected unique request paths")
    for case in cases:
        require(case["path"].startswith("/") and not case["path"].startswith("//") and
                case["status"] in (200, 404) and isinstance(case["body"], dict),
                f"Invalid request case: {case!r}")
    return cases


def policy():
    load_cases()
    require(CLUSTERS == {"aks-source": "simulated AKS source (kind)",
                         "eks-target": "simulated EKS target (kind)"}, "Missing simulation labels")
    require(PRIVATE["status"] == "unresolved" and PRIVATE["execution"] == "not run",
            "A private dependency must not be replayed")
    print(command("helm", "lint", CHART, *VALUES), end="")
    with tempfile.TemporaryDirectory() as tmp:
        manifest = Path(tmp) / "sandbox.yaml"
        data = Path(tmp) / "registries.json"
        data.write_text(json.dumps({"registries": {"approved": ["localhost/cmg-20261128/"]}}))
        manifest.write_text(command("helm", "template", APP, CHART, "-n", SANDBOX, *VALUES))
        base = ("conftest", "test", "--no-color")
        existing = ("--policy", STANDARD / "policy/conftest")
        for args in (
            (*existing, "--data", STANDARD / "base-images.yaml", "--parser", "dockerfile",
             "--namespace", "platform.dockerfile", SAMPLE / "Dockerfile"),
            (*existing, "--data", data, "--namespace", "platform.k8s", manifest),
            ("--policy", HERE / "policy.rego", "--namespace", "migration.local", manifest),
        ):
            print(command(*base, *args), end="")
    print(f"{RUN_ID}: 12 stable request cases; {', '.join(CLUSTERS.values())}")


def leftovers():
    host = os.environ.get("DOCKER_HOST") or command(
        "docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}").strip()
    require(host.startswith("unix://"), "The simulation requires a local Docker Unix socket")
    clusters = set(command("kind", "get", "clusters").splitlines()) & CLUSTERS.keys()
    names = command("docker", "ps", "-a", "--format", "{{.Names}}").splitlines()
    containers = [name for name in names if name.startswith(tuple(f"{c}-" for c in CLUSTERS))]
    return sorted(clusters), sorted(containers)


def check_teardown():
    clusters, containers = leftovers()
    print(f"{RUN_ID}: {', '.join(f'{c} ({s})' for c, s in CLUSTERS.items())}")
    print(f"kind clusters remaining: {clusters}")
    print(f"Docker containers remaining: {containers}")
    return not (clusters or containers)


def request(port, path, expected_status, expected_body):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        body = response.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except ValueError:
            parsed = None
        matches = response.status == expected_status and parsed == expected_body
        return {"status": "pass" if matches else "fail", "actual_status": response.status,
                "actual_body": body}
    except (OSError, http.client.HTTPException) as exc:
        return {"status": "fail", "error": str(exc)}
    finally:
        connection.close()


@contextlib.contextmanager
def port_forward(kubectl, pod, env):
    with tempfile.TemporaryFile() as log:
        process = subprocess.Popen((*kubectl, "port-forward", "--address", "127.0.0.1",
                                    f"pod/{pod}", ":8080"),
                                   env=env, stdout=subprocess.PIPE, stderr=log)
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                end = time.monotonic() + 20
                while time.monotonic() < end and selector.select(max(0, end - time.monotonic())):
                    line = process.stdout.readline().decode()
                    match = re.match(r"Forwarding from 127\.0\.0\.1:(\d+) -> 8080", line)
                    if match:
                        yield int(match.group(1))
                        return
                    if not line:
                        break
            log.seek(0)
            raise RuntimeError(f"Pod port-forward not ready: {log.read().decode()}")
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            process.stdout.close()


def ready_pod(kubectl, env):
    command(*kubectl, "rollout", "status", f"deployment/{APP}", "--timeout=120s", env=env)
    pods = json.loads(command(*kubectl, "get", "pods", "-l", f"app={APP}", "-o", "json", env=env))
    ready = []
    for pod in pods["items"]:
        if pod["metadata"].get("deletionTimestamp") or pod["status"].get("phase") != "Running":
            continue
        for container in pod["status"].get("containerStatuses", []):
            if container["name"] == APP and container["ready"]:
                image_id = container["imageID"]
                digest = re.search(r"sha256:[0-9a-f]{64}$", image_id)
                require(digest and container["image"] == IMAGE,
                        f"Unexpected running pod image: {container['image']}, imageID={image_id}")
                ready.append({"pod": pod["metadata"]["name"], "uid": pod["metadata"]["uid"],
                              "node": pod["spec"]["nodeName"], "image": container["image"],
                              "image_id": image_id, "digest": digest.group()})
    require(len(ready) == 1, f"Expected one Ready running pod, got {ready!r}")
    return ready[0]


def error_text(exc):
    if isinstance(exc, subprocess.TimeoutExpired):
        return f"{exc}\n{(exc.stdout or b'').decode(errors='replace')}"
    return str(exc)


def run_cluster(cluster, result, owned, env, save):
    context = result["identity"]["context"]
    kubectl = ("kubectl", "--context", context, "-n", SANDBOX)
    helm = ("helm", "--kube-context", context, "-n", SANDBOX)
    stage = "setup"
    try:
        owned.append(cluster)
        command("kind", "create", "cluster", "--name", cluster, "--image", NODE_IMAGE,
                "--wait", "120s", env=env)
        command("kind", "load", "docker-image", IMAGE, "--name", cluster, env=env)
        nodes = command(*kubectl, "get", "nodes", "-o", "name", env=env).splitlines()
        require(nodes == [f"node/{cluster}-control-plane"], f"Unexpected node identity: {nodes}")
        command(*helm, "install", APP, CHART, "--create-namespace", *VALUES, env=env)
        result["checks"][stage] = {"status": "pass", "nodes": nodes}
        save()

        stage = "readiness"
        initial = ready_pod(kubectl, env)
        result["checks"][stage] = {"status": "pass", **initial}
        save()

        # If forwarding cannot start, the request cases stay unrun; lifecycle checks can still run.
        try:
            with port_forward(kubectl, initial["pod"], env) as port:
                for result_case in result["requests"]:
                    case = result_case["expected"]
                    result_case.update(request(port, case["path"], case["status"], case["body"]))
                    save()
        except (OSError, RuntimeError) as exc:
            result["replay_error"] = str(exc)
            save()

        stage = "restart"
        result["checks"][stage] = {"status": "fail", "old_uid": initial["uid"]}
        command(*kubectl, "delete", "pod", initial["pod"], "--timeout=120s", env=env)
        replacement = ready_pod(kubectl, env)
        result["checks"][stage].update(replacement)
        require(initial["uid"] != replacement["uid"], "Restart did not replace the pod UID")
        with port_forward(kubectl, replacement["pod"], env) as port:
            probe = request(port, "/health", 200, {"status": "UP"})
        result["checks"][stage]["health"] = probe
        require(probe["status"] == "pass", "Replacement pod did not return the health contract")
        result["checks"][stage]["status"] = "pass"
        save()

        stage = "sandbox_rollback"
        result["checks"][stage] = {"status": "fail"}
        greeting = "sandbox revision two"
        command(*helm, "upgrade", APP, CHART, *VALUES, "--set-string", f"env.GREETING={greeting}", env=env)
        updated = ready_pod(kubectl, env)
        with port_forward(kubectl, updated["pod"], env) as port:
            changed = request(port, "/", 200, {"message": greeting})
        result["checks"][stage]["revision_2"] = {**updated, "response": changed}
        save()
        command(*helm, "rollback", APP, "1", "--wait", "--timeout", "120s", env=env)
        restored = ready_pod(kubectl, env)
        with port_forward(kubectl, restored["pod"], env) as port:
            baseline = request(port, "/", 200, next(
                case["expected"]["body"] for case in result["requests"] if case["expected"]["path"] == "/"))
        result["checks"][stage]["restored_revision_1"] = {**restored, "response": baseline}
        require(changed["status"] == baseline["status"] == "pass",
                "Sandbox upgrade or rollback did not return the expected greeting")
        result["checks"][stage]["status"] = "pass"
    except (OSError, RuntimeError, subprocess.TimeoutExpired, ValueError) as exc:
        result["checks"][stage].update(status="fail", error=error_text(exc))
    finally:
        save()


def record(path, data):
    pending = path.with_suffix(".tmp")
    pending.write_text(json.dumps(data, indent=2) + "\n")
    pending.replace(path)


def run(output):
    cases = load_cases()
    output.mkdir(parents=True)
    results = {
        cluster: {"run_id": RUN_ID, "identity": identity(cluster), "limitation": LIMITATION,
                  "private_dependency": PRIVATE, "checks": {key: {"status": "unrun"} for key in CHECKS},
                  "requests": [{"expected": case, "status": "unrun"} for case in cases]}
        for cluster in CLUSTERS
    }
    summary = {"run_id": RUN_ID, "simulations": [identity(c) for c in CLUSTERS],
               "limitation": LIMITATION, "private_dependency": PRIVATE,
               "image_parity": {"status": "unrun"}, "teardown": {"status": "unrun"}}

    def save_cluster(cluster):
        result = results[cluster]
        result["request_counts"] = {status: sum(c["status"] == status for c in result["requests"])
                                    for status in ("pass", "fail", "unrun")}
        record(output / f"{cluster}.json", result)

    for cluster in CLUSTERS:
        save_cluster(cluster)
    record(output / "summary.json", summary)
    owned = []
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ, KUBECONFIG=str(Path(tmp) / "kubeconfig"), KIND_EXPERIMENTAL_PROVIDER="docker")
        try:
            require(not any(leftovers()), "Refusing to change existing simulation clusters or containers")
            command("docker", "build", "-t", IMAGE, str(SAMPLE), timeout=600)
            summary["built_image"] = {"tag": IMAGE, "docker_image_id": command(
                "docker", "image", "inspect", IMAGE, "--format", "{{.Id}}").strip()}
            record(output / "summary.json", summary)
            for cluster in CLUSTERS:
                run_cluster(cluster, results[cluster], owned, env, lambda: save_cluster(cluster))
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            summary["setup_error"] = error_text(exc)
        finally:
            cleanup_errors = {}
            for cluster in owned:
                try:
                    command("kind", "delete", "cluster", "--name", cluster, env=env)
                except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
                    cleanup_errors[cluster] = error_text(exc)
            try:
                clean = check_teardown()
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
                clean = False
                cleanup_errors["verification"] = error_text(exc)
            summary["teardown"] = {"status": "pass" if clean and not cleanup_errors else "fail",
                                   "errors": cleanup_errors}
            record(output / "summary.json", summary)

    digests = {}
    for cluster, result in results.items():
        checks = result["checks"]
        pods = (checks["readiness"], checks["restart"],
                checks["sandbox_rollback"].get("revision_2", {}),
                checks["sandbox_rollback"].get("restored_revision_1", {}))
        digests[cluster] = [pod["digest"] for pod in pods if "digest" in pod]
        print(f"{cluster} ({CLUSTERS[cluster]}): {result['request_counts']}; "
              "private dependency unresolved/not run")
    if all(digests.values()):
        unique = {digest for values in digests.values() for digest in values}
        summary["image_parity"] = {"status": "pass" if len(unique) == 1 else "fail",
                                   "running_pod_digests": digests}
    record(output / "summary.json", summary)
    print(f"Running pod digest parity: {summary['image_parity']}")
    print(LIMITATION)
    return (summary["teardown"]["status"] == summary["image_parity"]["status"] == "pass" and
            all(r["request_counts"]["pass"] == len(cases) and
                all(check["status"] == "pass" for check in r["checks"].values()) for r in results.values()))


def main():
    parser = argparse.ArgumentParser(description=f"{RUN_ID}: {LIMITATION}")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("policy")
    sub.add_parser("check-teardown")
    execute = sub.add_parser("run")
    execute.add_argument("--output", type=Path, required=True, help="new directory for simulation results")
    args = parser.parse_args()
    if args.command == "policy":
        policy()
        return 0
    if args.command == "check-teardown":
        return 0 if check_teardown() else 1
    return 0 if run(args.output) else 1


if __name__ == "__main__":
    raise SystemExit(main())
