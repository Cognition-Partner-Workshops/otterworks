import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import connectivity_matrix as network
import control_ledger
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
