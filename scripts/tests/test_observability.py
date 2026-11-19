import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


generator = load("gen-slo-rules")
runbooks = load("check-runbooks")


class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self.spec = yaml.safe_load((ROOT / "observability/slo/slos.yaml").read_text())

    def test_all_services_and_windows(self):
        groups = generator.generate(self.spec)["groups"]
        self.assertEqual(len(groups), 6)
        for group in groups:
            records = [r["record"] for r in group["rules"] if "record" in r]
            for window in generator.WINDOWS:
                self.assertEqual(records.count(f"slo:error_ratio:rate{window}"), 2)
            alerts = [r for r in group["rules"] if "alert" in r]
            self.assertEqual(len(alerts), 8)
            self.assertEqual({r["labels"]["severity"] for r in alerts}, {"page", "ticket"})
            self.assertTrue(all("runbook_url" in r["annotations"] for r in alerts))

    def test_empty_services_rejected(self):
        self.spec["services"] = {}
        with self.assertRaises(ValueError):
            generator.generate(self.spec)

    def test_invalid_objective_and_selector_rejected(self):
        for objective in (0, 1, -1):
            spec = copy.deepcopy(self.spec)
            spec["services"]["api-gateway"]["availability"]["objective"] = objective
            with self.assertRaises(ValueError):
                generator.generate(spec)
        with self.assertRaises(ValueError):
            generator.selector("sum(metric)", "api-gateway")


class RunbookTests(unittest.TestCase):
    def check_content(self, content):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rules.yml"
            path.write_text(content)
            return runbooks.check([path])

    def test_existing_and_empty(self):
        count, errors = runbooks.check([ROOT / "observability/prometheus/alerts.yml"])
        self.assertGreater(count, 0)
        self.assertEqual(errors, [])
        self.assertEqual(self.check_content("groups: []"), (0, []))

    def test_missing_annotation_and_target(self):
        for annotation in ("{}", "{runbook_url: '" + runbooks.PREFIX + "absent.md'}"):
            _, errors = self.check_content(
                "groups: [{rules: [{alert: Test, annotations: " + annotation + "}]}]")
            self.assertEqual(len(errors), 1)


if __name__ == "__main__":
    unittest.main()
