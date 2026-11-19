import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


seed = load("seed", "infrastructure/k8s/odl-mocks/seed.py")
routing = load("routing", "scripts/odl/route-alerts.py")


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
