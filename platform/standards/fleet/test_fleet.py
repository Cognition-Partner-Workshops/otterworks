import json
from pathlib import Path
import runpy
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import fleet
import load_compare


def workload(cpu="100m", owner="edge"):
    return {"apiVersion": "apps/v1", "kind": "Deployment",
            "metadata": {"name": "edge", "labels": {"owner": owner}},
            "spec": {"template": {"spec": {"containers": [
                {"name": "app", "resources": {"requests": {"cpu": cpu}}}
            ]}}}}


class FleetTests(unittest.TestCase):
    def test_demo_replays_recorded_drift_without_a_cluster(self):
        demo = fleet.HERE.parents[2] / "demos" / "devops"
        runner = runpy.run_path(str(demo / "drift_check.py"))
        fixture = json.loads((demo / "fixtures" / "observed-deployments.json").read_text(encoding="utf-8"))
        desired = {item["metadata"]["name"]: item for item in fixture["items"]}
        collab = desired["collab-service"]
        collab["metadata"]["labels"]["owner"] = "collaboration"
        collab["spec"]["template"]["spec"]["containers"][0]["resources"]["requests"] = {"cpu": "100m"}
        collab["spec"]["template"]["spec"]["containers"][0]["readinessProbe"]["httpGet"]["path"] = "/ignored"

        def render(command, **kwargs):
            self.assertEqual(["helm", "template"], command[:2])
            self.assertEqual("templates/deployment.yaml", command[-1])
            self.assertFalse(kwargs.get("shell"))
            return SimpleNamespace(stdout=json.dumps(desired[command[2]]))

        with TemporaryDirectory() as root:
            markdown = Path(root) / "drift.md"
            report = Path(root) / "drift.json"
            with patch("sys.argv", ["drift_check.py", "--markdown", str(markdown), "--json", str(report)]):
                with patch("subprocess.run", side_effect=render) as helm:
                    self.assertEqual(1, runner["main"]())
            data = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(6, helm.call_count)
            self.assertEqual(6, data["resources_checked"])
            self.assertEqual("RED", data["result"])
            self.assertEqual("fixture: recorded, not live AWS", data["observed"]["label"])
            self.assertEqual(
                [("/metadata/labels/owner", "collaboration", None),
                 ("/spec/template/spec/containers/collab-service/resources/requests",
                  {"cpu": "100m"}, {"cpu": "320m", "memory": "128Mi"})],
                [(row["field"], row["desired"], row["observed"]) for row in data["changes"]],
            )
            self.assertIn("**RED**", markdown.read_text(encoding="utf-8"))

    def test_drift_preserves_declared_request_and_owner_changes(self):
        current = workload("300m")
        current["metadata"]["labels"] = {"managed-by": "helm"}
        current["metadata"]["uid"] = "different"
        current["status"] = {"readyReplicas": 0}
        report = fleet.drift([workload()], [current], "dev")
        self.assertEqual({
            ("/metadata/labels/owner", "missing"),
            ("/spec/template/spec/containers/app/resources/requests/cpu", "changed"),
        }, {(item["field"], item["state"]) for item in report["changes"]})

    def test_live_uses_explicit_context_and_buffers_get_json(self):
        process = SimpleNamespace(stdout=json.dumps(workload()))
        with patch("fleet.subprocess.run", return_value=process) as run:
            self.assertEqual([workload()], fleet.live_objects("kind-test", "dev", [workload()]))
        command = run.call_args.args[0]
        self.assertEqual(["kubectl", "--context", "kind-test", "--namespace", "dev", "get"], command[:6])
        self.assertIn("kind: Deployment", run.call_args.kwargs["input"])

    def test_manifest_stream_and_catalog_counts(self):
        with TemporaryDirectory() as root:
            path = Path(root) / "manifests.yaml"
            path.write_text(
                "apiVersion: policy/v1beta1\nkind: PodDisruptionBudget\nmetadata: {name: quota}\n"
                "---\nkind: List\nitems:\n"
                "- {apiVersion: v1, kind: Service, metadata: {name: svc}}\n"
                "- {apiVersion: v1, kind: Endpoints, metadata: {name: svc}}\n", encoding="utf-8")
            catalog = json.loads((fleet.HERE / "api-catalog.json").read_text(encoding="utf-8"))
            for target in catalog["targets"]:
                with self.subTest(target=target):
                    report = fleet.api_compat(fleet.documents(path), target, catalog, "default")
                    self.assertEqual(dict(removed=1, deprecated=1, no_catalog_finding=1), report["counts"])

    def test_board_preserves_holds_and_requires_ready_evidence(self):
        inventory = {"workloads": [
            {"workload": "api|edge", "status": "held"},
            {"workload": "worker", "status": "rejected"},
        ]}
        result = fleet.board(inventory)
        self.assertIn("api&#124;edge", result)
        self.assertIn("ready: 0, held: 1, rejected: 1", result)
        inventory["workloads"][0]["status"] = "ready"
        with self.assertRaises(ValueError):
            fleet.board(inventory)

    def test_bounded_load_preserves_before_and_requires_equal_profile(self):
        profile = dict(requests=3, rate_per_second=3, concurrency=2, timeout_seconds=1,
                       sample_seconds=1, p95_limit_ms=100, allowed_failures=0)
        load_compare.validate(profile)
        url = load_compare.target("http://127.0.0.1:9910/work")
        initial = dict(cpu_millicores=20, pods={"a": 0}, replicas=1, ready_replicas=1)
        final = dict(cpu_millicores=80, pods={"a": 1, "b": 0}, replicas=2, ready_replicas=2)
        with patch("load_compare.emit_load", return_value=[(200, 10), (200, 130), (None, 500)]):
            with patch("load_compare.time.sleep"), patch("load_compare.snapshot") as sample:
                sample.side_effect = lambda: initial if sample.call_count == 1 else final
                before = load_compare.measure(profile, url, sample)
        self.assertFalse(before["passed"])
        self.assertEqual((130, 1, 80, 1, 2), tuple(before[key] for key in (
            "p95_ms", "failures", "cpu_peak_millicores", "restarts_on_retained_pods", "replicas_after"
        )))
        after = dict(before, p95_ms=60, failures=0, passed=True)
        self.assertIn("| passed | false | true |", load_compare.render(load_compare.compare(before, after)))
        with self.assertRaises(ValueError):
            load_compare.compare(before, dict(after, endpoint="/different"))
        with self.assertRaises(ValueError):
            load_compare.target("http://example.com:9910/work")
