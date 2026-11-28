"""Local-dev injected demo for CMG_20261128: a readiness probe drift on eks-target only.

Runs the frozen replay harness unchanged, except that the eks-target Helm install points the
readiness/liveness probe at a path the sample service does not serve. The red result is the
point of the demo; the repair is to rerun ``replay.py run`` without this wrapper.
Local kind simulation only; this does not prove live AKS parity.
"""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, os.environ.get("CMG_REPLAY_DIR", str(Path(__file__).resolve().parent)))
import replay  # noqa: E402

TARGET = "eks-target"
DRIFT_PATH = "/ready"
INJECTED = {"kind": "injected_demo", "scope": "local-dev kind only", "cluster": TARGET,
            "drift": "readiness probe", "override": f"probes.path={DRIFT_PATH}",
            "expected": "eks-target readiness fails; aks-source unaffected"}


def install(target=TARGET):
    base_values, run_cluster, ready_pod = replay.VALUES, replay.run_cluster, replay.ready_pod
    current = {}

    def drifted_run_cluster(cluster, result, owned, env, save):
        if cluster != target:
            return run_cluster(cluster, result, owned, env, save)
        replay.VALUES = (*base_values, "--set-string", INJECTED["override"])
        result["injected_demo"] = INJECTED
        current["result"] = result
        try:
            return run_cluster(cluster, result, owned, env, save)
        finally:
            replay.VALUES = base_values
            current.clear()

    def observed_ready_pod(kubectl, env):
        try:
            return ready_pod(kubectl, env)
        except RuntimeError:
            if "result" in current:
                current["result"]["injected_demo_observed"] = {
                    name: replay.command(*kubectl, *args, env=env) for name, args in (
                        ("pods", ("get", "pods", "-o", "wide")),
                        ("probe", ("get", "deployment", replay.APP, "-o",
                                   "jsonpath={.spec.template.spec.containers[0].readinessProbe}")),
                        ("events", ("get", "events", "--sort-by=.lastTimestamp")))}
            raise

    replay.run_cluster, replay.ready_pod = drifted_run_cluster, observed_ready_pod


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, required=True, help="new directory for red results")
    args = parser.parse_args()
    install()
    green = replay.run(args.output)
    summary = json.loads((args.output / "summary.json").read_text())
    summary["injected_demo"] = INJECTED
    replay.record(args.output / "summary.json", summary)
    print(f"Injected demo ({TARGET} readiness drift) expected red; harness green={green}")
    return 0 if not green else 1


if __name__ == "__main__":
    raise SystemExit(main())
