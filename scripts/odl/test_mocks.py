import importlib.util
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


seed = load("seed", "infrastructure/k8s/odl-mocks/seed.py")
confluence = load("confluence_seed", "infrastructure/k8s/odl-mocks/confluence-seed.py")
routing = load("routing", "scripts/odl/route-alerts.py")


class NetworkPolicyTests(unittest.TestCase):
    def test_only_controller_and_monitoring_namespaces(self):
        policies = list(yaml.safe_load_all(
            (ROOT / "infrastructure/k8s/odl-mocks/networkpolicy.yaml").read_text()))
        self.assertEqual({p["metadata"]["name"] for p in policies}, {"jira", "pagerduty", "confluence"})
        for policy in policies:
            self.assertEqual(policy["metadata"]["namespace"], "odl-mocks")
            self.assertEqual(policy["metadata"]["labels"]["run_token"], "odl-1795112287")
            self.assertEqual(policy["spec"]["podSelector"],
                             {"matchLabels": {"app": policy["metadata"]["name"]}})
            self.assertEqual(policy["spec"]["ingress"], [{"from": [
                {"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": ns}}}
                for ns in ("ingress-nginx", "monitoring")], "ports": [{"protocol": "TCP", "port": 8080}]}])


class SeedTests(unittest.TestCase):
    def test_missing_created_and_existing_unchanged(self):
        issue = {"seed_label": "odl-test", "fields": {"summary": "Example"}}
        with patch.object(seed, "request", side_effect=[{"issues": []}, {"key": "ENG-4"}]) as call:
            seed.reconcile([issue])
            self.assertEqual(call.call_args.args, ("/rest/api/3/issue", {"fields": issue["fields"]}))
        with patch.object(seed, "request", return_value={"issues": [{"key": "ENG-4"}]}) as call:
            seed.reconcile([issue])
            self.assertEqual(call.call_count, 1)

    def test_empty_and_api_failure(self):
        with patch.object(seed, "request") as call:
            seed.reconcile([])
            call.assert_not_called()
        with patch.object(seed, "request", side_effect=ConnectionError):
            with self.assertRaises(ConnectionError):
                seed.reconcile([{"seed_label": "odl-test"}])

    def test_story_contract(self):
        issues = json.loads((ROOT / "infrastructure/k8s/odl-mocks/seed.json").read_text())
        self.assertEqual(len(issues), 3)
        self.assertEqual(len({i["seed_label"] for i in issues}), 3)
        for issue in issues:
            fields = issue["fields"]
            self.assertIn(issue["seed_label"], fields["labels"])
            self.assertIn("odl-seed", fields["labels"])
            self.assertIn("Acceptance criteria", fields["description"])
            self.assertTrue(3 <= fields["description"].count("- [ ]") <= 5)


class ConfluenceTests(unittest.TestCase):
    def test_scoped_resources(self):
        objects = list(yaml.safe_load_all(subprocess.check_output(
            ["kubectl", "kustomize", str(ROOT / "infrastructure/k8s/odl-mocks")], text=True)))
        scoped = [o for o in objects if o["metadata"]["labels"].get("app") == "confluence"]
        self.assertEqual(len(scoped), 5)
        self.assertEqual({o["kind"] for o in scoped},
                         {"Deployment", "Service", "Ingress", "NetworkPolicy", "ConfigMap"})
        self.assertTrue(all(o["metadata"]["labels"]["run_token"] == "odl-1795112287" for o in scoped))

    def test_ingress_paths_and_secret(self):
        objects = list(yaml.safe_load_all((ROOT / "infrastructure/k8s/odl-mocks/confluence.yaml").read_text()))
        ingress = next(o for o in objects if o["kind"] == "Ingress")
        self.assertEqual(ingress["metadata"]["annotations"]["nginx.ingress.kubernetes.io/auth-secret"],
                         "confluence-mock-basic-auth")
        rule = ingress["spec"]["rules"][0]
        self.assertEqual(rule["host"], "confluence-odl.demo.otterworks.app")
        self.assertEqual([p["path"] for p in rule["http"]["paths"]], ["/wiki", "/static"])

    def test_missing_and_existing_pages(self):
        page = {"title": "Example", "body": {"representation": "storage", "value": "<p>Example</p>"}}
        with patch.object(confluence, "request", side_effect=[{"results": [{"id": "2"}]},
                          {"results": []}, {"id": "203"}]) as call:
            confluence.reconcile([page])
            self.assertEqual(call.call_args.args, ("/pages", {"spaceId": "2", **page}))
            self.assertEqual(call.call_args_list[1].args, ("/pages?space-id=2&title=Example",))
        with patch.object(confluence, "request", side_effect=[{"results": [{"id": "2"}]},
                          {"results": [{"id": "203"}]}]) as call:
            confluence.reconcile([page])
            self.assertEqual(call.call_count, 2)

    def test_empty_and_errors(self):
        with patch.object(confluence, "request") as call:
            confluence.reconcile([])
            call.assert_not_called()
        for result in ({"results": []}, {"results": [{"id": "2"}, {"id": "3"}]}):
            with patch.object(confluence, "request", return_value=result):
                with self.assertRaises(ValueError):
                    confluence.reconcile([{"title": "Example"}])
        with patch.object(confluence, "request", side_effect=ConnectionError):
            with self.assertRaises(ConnectionError):
                confluence.reconcile([{"title": "Example"}])

    def test_page_contract(self):
        pages = json.loads((ROOT / "infrastructure/k8s/odl-mocks/confluence-seed.json").read_text())
        self.assertEqual([p["title"] for p in pages], ["REST API conventions", "Customer source mapping"])
        for page in pages:
            self.assertEqual(page["body"]["representation"], "storage")
        for term in ("/api/v1/", "snake_case", "decimal strings", "pagination", "contract"):
            self.assertIn(term, pages[0]["body"]["value"])
        for term in ("CUSTMAST", "ACCOUNTS", "crm.contacts", "MongoDB", "open question"):
            self.assertIn(term, pages[1]["body"]["value"])


class RoutingTests(unittest.TestCase):
    def test_routing_key_lookup_and_empty_result(self):
        with patch.object(routing.subprocess, "check_output", return_value="fixture-key\n"):
            self.assertEqual(routing.pagerduty_routing_key(), "fixture-key")
        with patch.object(routing.subprocess, "check_output", return_value="\n"):
            with self.assertRaises(ValueError):
                routing.pagerduty_routing_key()
        with patch.object(routing.subprocess, "check_output", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                routing.pagerduty_routing_key()

    def config(self):
        return {"route": {"receiver": "null", "routes": [{"receiver": "other"}]},
                "receivers": [{"name": "other", "webhook_configs": [{"url": "http://example.invalid"}]},
                              {"name": "devin-oncall", "webhook_configs": [
                                  {"url": "https://example.invalid", "send_resolved": False}]}]}

    def test_preserves_routes_other_receivers_and_is_idempotent(self):
        original = self.config()
        updated, url = routing.updated_config(original)
        self.assertEqual(url, "https://example.invalid")
        self.assertEqual(original["route"], updated["route"])
        self.assertEqual(original["receivers"][0], updated["receivers"][0])
        self.assertIn("url", original["receivers"][1]["webhook_configs"][0])
        again, url = routing.updated_config(updated)
        self.assertIsNone(url)
        self.assertEqual(updated, again)
        self.assertNotIn("example.invalid", json.dumps(routing.structure(updated)))

    def test_missing_or_ambiguous_receiver_rejected(self):
        for receivers in ([], [{"name": "devin-oncall", "webhook_configs": []}]):
            with self.assertRaises(ValueError):
                routing.updated_config({"receivers": receivers})


if __name__ == "__main__":
    unittest.main()
