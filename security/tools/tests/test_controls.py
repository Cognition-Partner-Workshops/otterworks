import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import connectivity_matrix as network
import control_ledger
import control_report
import iam_plan
import rls_assertions


def statement(actions, resource, effect="Allow"):
    return {"Effect": effect, "Action": actions, "Resource": resource}


class IamPlanTests(unittest.TestCase):
    def test_approved_excess_and_denial(self):
        scope = {"address": "aws_iam_role_policy.fixture", "allow": [
            {"action": "s3:GetObject", "resource": "arn:aws:s3:::example/object"},
        ]}
        resource = scope["allow"][0]["resource"]
        plan = {"resource_changes": [{"address": scope["address"], "type": "aws_iam_role_policy", "change": {
            "after": {"policy": json.dumps({"Statement": [statement("s3:Get*", resource)]})},
        }}]}
        rows = iam_plan.evaluate(plan, scope)
        self.assertEqual([(x["check"], x["passed"]) for x in rows], [("approved path", True), ("excess allow", False)])
        plan["resource_changes"][0]["change"]["after"]["policy"] = json.dumps({"Statement": [
            statement("S3:GetObject", resource),
            statement("s3:GetObject", resource, "Deny"),
        ]})
        self.assertEqual([x["passed"] for x in iam_plan.evaluate(plan, scope)], [False])

    def test_rejects_incomplete_arns_in_approvals_and_policies(self):
        action, incomplete = "sqs:ReceiveMessage", "arn:aws:sqs"
        scope = {"address": "aws_iam_role_policy.fixture", "allow": [{"action": action, "resource": incomplete}]}
        plan = {"resource_changes": [{"address": scope["address"], "type": "aws_iam_role_policy", "change": {
            "after": {"policy": json.dumps({"Statement": statement(action, incomplete)})},
        }}]}
        with self.assertRaisesRegex(ValueError, "scope resources must be complete ARNs"):
            iam_plan.evaluate(plan, scope)
        scope["allow"][0]["resource"] = "arn:aws:sqs:us-east-1:123456789012:synthetic-queue"
        with self.assertRaisesRegex(ValueError, "incomplete or non-ARN policy resources"):
            iam_plan.evaluate(plan, scope)


class RlsTests(unittest.TestCase):
    def setUp(self):
        self.spec = {"table": "app.records", "roles": {"reader": "READER_DSN"}, "assertions": [
            {"role": "reader", "name": "own", "access": "allow", "expected_count": 10, "sql": "SELECT 10"},
            {"role": "reader", "name": "other", "access": "deny", "expected_count": 0, "sql": "SELECT 0"},
        ]}

    def test_owner_is_rejected_before_assertions(self):
        def query(_, sql):
            self.assertIn("pg_has_role(c.relowner, 'MEMBER')", sql)
            return "owns table or can assume its owner"

        with self.assertRaisesRegex(ValueError, "refusing reader"):
            rls_assertions.run(self.spec, {"reader": "fixture"}, query)

    def test_counts_as_supplied_role(self):
        def query(dsn, sql):
            self.assertEqual(dsn, "fixture")
            return {"SELECT 10": "10", "SELECT 0": "2"}.get(sql, "ok")

        self.assertEqual([x["passed"] for x in rls_assertions.run(self.spec, {"reader": "fixture"}, query)], [True, False])

    def test_connection_url_is_passed_as_separate_libpq_values(self):
        self.assertEqual(rls_assertions.connection_env("postgresql://reader:synthetic%40local@localhost:5433/fixture?sslmode=require"), {
            "PGHOST": "localhost", "PGPORT": "5433", "PGUSER": "reader", "PGDATABASE": "fixture",
            "PGPASSWORD": "synthetic@local", "PGSSLMODE": "require",
        })


class NetworkTests(unittest.TestCase):
    def test_namespace_less_helm_policies_use_release_namespace_only_when_given(self):
        policy = {"kind": "NetworkPolicy", "metadata": {"name": "document-service"},
                  "spec": {"podSelector": {"matchLabels": {"app": "docs"}}, "ingress": [
                      {"from": [{"podSelector": {}}]},
                  ]}}
        explicit = {**policy, "metadata": {"name": "explicit-policy", "namespace": "explicit"},
                    "spec": {"podSelector": {}, "ingress": [{}]}}
        source = {"namespace": "unrelated"}
        dest = {"namespace": "otterworks-demo", "labels": {"app": "docs"}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "policies.json"
            path.write_text(json.dumps({"kind": "List", "items": [policy, explicit]}))
            with self.assertRaisesRegex(ValueError, "document-service has no namespace; pass --policy-namespace"):
                network.policies_from([path])
            rules = network.policies_from([path], "otterworks-demo")
        self.assertEqual([rule["metadata"]["namespace"] for rule in rules], ["otterworks-demo", "explicit"])
        self.assertFalse(network.offline_allowed(rules, {}, source, dest, "TCP", 8080))

    def test_live_runtime_failure_is_reported_and_selected_container_is_used(self):
        gateway = {"namespace": "demo", "pod": "gateway"}
        matrix = {"pods": {"default": gateway, "sidecar": {**gateway, "probe_container": "probe"},
                           "docs": {"namespace": "demo", "pod": "docs"}}, "checks": [
            {"source": "default", "destination": "docs", "port": 80, "expected": "deny"},
            {"source": "default", "destination": "docs", "port": 81, "expected": "allow"},
            {"source": "sidecar", "destination": "docs", "port": 80, "expected": "allow"},
        ]}
        kubectl = ["kubectl", "--context", "kind-demo", "-n", "demo"]
        default_exec = [*kubectl, "exec", "gateway", "--", "python3", "-c"]
        sidecar_exec = [*kubectl, "exec", "gateway", "-c", "probe", "--", "python3", "-c"]
        commands = []

        def execute(command, **kwargs):
            commands.append(command)
            if command == [*default_exec, "import socket"]:
                raise subprocess.CalledProcessError(126, command)
            return {tuple([*sidecar_exec, "import socket"]): "",
                    tuple([*kubectl, "get", "pod", "docs", "-o", "json"]): '{"status": {"podIP": "10.0.0.2"}}',
                    tuple([*sidecar_exec, network.PROBE, "10.0.0.2", "80"]): "allowed\n"}[tuple(command)]

        stderr = io.StringIO()
        with patch.object(network.subprocess, "check_output", side_effect=execute), redirect_stderr(stderr):
            probe = network.live_runner("kind-demo", matrix)
            self.assertIn("Probe runtime unavailable in demo/gateway (container: default)", stderr.getvalue())
            rows = network.run(matrix, probe)
        self.assertEqual(commands[:2], [[*default_exec, "import socket"], [*sidecar_exec, "import socket"]])
        self.assertEqual(len(commands), 4)
        self.assertEqual([(row["actual"], row["passed"]) for row in rows],
                         [("error", False), ("error", False), ("allowed", True)])

    def test_ingress_and_egress_allow_union_with_namespace_selector_and_named_port(self):
        source = {"namespace": "client", "labels": {"role": "trusted"}}
        dest = {"namespace": "server", "labels": {"app": "docs"}, "ports": [{"name": "http", "port": 8080}]}
        policy = lambda ns, **spec: {"metadata": {"namespace": ns}, "spec": {"podSelector": {}, **spec}}
        deny_ingress = policy("server", policyTypes=["Ingress"])
        deny_egress = policy("client", policyTypes=["Egress"])
        allow_ingress = policy("server", ingress=[{
            "from": [{"namespaceSelector": {"matchLabels": {"zone": "front"}},
                      "podSelector": {"matchExpressions": [{"key": "role", "operator": "In", "values": ["trusted"]}]}}],
            "ports": [{"port": "http"}],
        }])
        allow_egress = policy("client", policyTypes=["Egress"], egress=[{
            "to": [{"namespaceSelector": {"matchLabels": {"zone": "backend"}}}], "ports": [{"port": 8080}],
        }])
        rules = [deny_ingress, deny_egress, allow_ingress, allow_egress]
        labels = {"client": {"zone": "front"}, "server": {"zone": "backend"}}
        self.assertTrue(network.offline_allowed(rules, labels, source, dest, "TCP", 8080))
        self.assertFalse(network.offline_allowed(rules[:-1], labels, source, dest, "TCP", 8080))
        self.assertFalse(network.offline_allowed(rules, labels, source, dest, "TCP", 8081))

    def test_network_error_never_counts_as_a_denial(self):
        matrix = {"pods": {"src": {}, "dst": {}}, "checks": [
            {"source": "src", "destination": "dst", "port": 80, "expected": "deny"},
        ]}
        self.assertTrue(network.run(matrix, lambda *_: "denied")[0]["passed"])
        self.assertFalse(network.run(matrix, lambda *_: "error")[0]["passed"])


class LedgerTests(unittest.TestCase):
    def test_unowned_cannot_close(self):
        check = {"result": "pass", "reference": "report.json"}
        row = {"control": "test", "owner": None, "evidence": {"commit": "abc"}, "status": "closed",
               "before": check, "after": check, "approved_path": check}
        with self.assertRaisesRegex(ValueError, "requires an owner"):
            control_ledger.ledger([row])
        rows, summary = control_ledger.ledger([{**row, "status": "amber"}])
        self.assertEqual(rows[0]["owner"], None)
        self.assertEqual(summary, {"closed": 0, "held": 0, "amber": 1})

    def test_cli_writes_json_and_markdown(self):
        check = {"result": "pass", "reference": "report.json"}
        row = {"control": "control-a", "owner": "team", "evidence": {"commit": "abc"}, "status": "closed",
               "before": check, "after": check, "approved_path": check}
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp) / "a.json"
            evidence.write_text(json.dumps(row))
            output = Path(tmp) / "ledger"
            subprocess.run([sys.executable, str(Path(control_ledger.__file__)), str(evidence),
                            "--output", str(output)], check=True)
            self.assertEqual(json.loads(output.with_suffix(".json").read_text())["checks"], [row])
            self.assertIn("| control-a | team |", output.with_suffix(".md").read_text())


class ReportTests(unittest.TestCase):
    def test_dotted_stems_keep_before_and_after_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            for phase, passed in (("before", False), ("after", True)):
                control_report.assertion_report(Path(tmp) / f"review.{phase}", phase, [{"passed": passed}],
                                                [("passed", "Passed")])
            for phase, passed in (("before", False), ("after", True)):
                output = Path(tmp) / f"review.{phase}"
                self.assertEqual(json.loads(Path(f"{output}.json").read_text())["checks"], [{"passed": passed}])
                self.assertIn(f"# {phase}\n", Path(f"{output}.md").read_text())
