import datetime as dt
import importlib.util
from itertools import takewhile
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from types import ModuleType
import unittest
from unittest.mock import Mock, patch


FAULTS = Path(__file__).resolve().parent
ROOT = FAULTS.parents[2]
PARITY = ROOT / "services/legacy-portal/parity"
RENDERER = FAULTS / "target-readiness/post-render.sh"


def read_json(path):
    return json.loads(path.read_text())


def contains_created_at(body):
    if isinstance(body, dict):
        return "createdAt" in body or any(map(contains_created_at, body.values()))
    return isinstance(body, list) and any(map(contains_created_at, body))


class ManifestTests(unittest.TestCase):
    def setUp(self):
        register = read_json(ROOT / "demos/app/complexity-manifest.json")
        self.classes = {entry["id"]: entry for entry in register["classes"]}
        self.assertEqual(
            list(self.classes),
            [f"MIG-{n:02}" for n in range(1, 8)] + ["CLD-01", "CLD-02", "CLD-03"],
        )
        self.assertEqual(len(register["classes"]), len(self.classes))

    def test_direct_timestamp_cases_have_a_created_at_response(self):
        c = self.classes["CLD-01"]
        planted = c["planted_keys"]
        downstream = c["downstream_keys"]
        requests = {case["id"] for case in read_json(PARITY / "requests.json")["cases"]}
        recorded = {
            case["id"]: case["response"] for case in read_json(PARITY / "java-reference.json")["cases"]
        }
        self.assertTrue(planted)
        self.assertEqual(planted, sorted(set(planted)))
        self.assertEqual(downstream, sorted(set(downstream)))
        self.assertLessEqual(set(planted + downstream), requests)
        self.assertTrue(set(planted).isdisjoint(downstream))
        self.assertEqual(c["expected_count"], len(planted))
        for case_id in planted:
            with self.subTest(case_id=case_id):
                self.assertTrue(contains_created_at(json.loads(recorded[case_id]["body"])))
        for case_id in downstream:
            with self.subTest(case_id=case_id):
                self.assertFalse(contains_created_at(json.loads(recorded[case_id]["body"])))

    def test_private_dependency_is_held_without_endpoint(self):
        c = self.classes["CLD-03"]
        held = read_json(ROOT / c["fixture"] / "held.json")
        self.assertEqual((c["status"], held["status"], held["execution"]), ("held", "held", "not run"))
        self.assertIsNone(held["endpoint"])


class TimestampDriftTests(unittest.TestCase):
    def setUp(self):
        dataapi = ModuleType("dataapi")
        self.baseline_field = dataapi.field = Mock(side_effect=lambda value: {"original": value})
        spec = importlib.util.spec_from_file_location("drift", FAULTS / "lambda-timestamp-drift/drift.py")
        self.drift = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, dataapi=dataapi):
            spec.loader.exec_module(self.drift)

    def test_datetime_uses_iso_format_with_an_offset(self):
        naive = dt.datetime(2026, 10, 1, 13, 24, 37, 245219)
        aware = naive.replace(tzinfo=dt.timezone(dt.timedelta(hours=-4)))
        self.assertEqual(self.drift.drift_field(naive), {"stringValue": "2026-10-01T13:24:37.245219+00:00"})
        self.assertEqual(self.drift.drift_field(aware), {"stringValue": "2026-10-01T13:24:37.245219-04:00"})
        self.baseline_field.assert_not_called()

    def test_non_datetime_fields_delegate_unchanged(self):
        for value in (None, "", 0, dt.date(2026, 10, 1)):
            with self.subTest(value=value):
                self.assertEqual(self.drift.drift_field(value), {"original": value})
                self.baseline_field.assert_called_with(value)

    def test_baseline_errors_are_not_swallowed(self):
        self.baseline_field.side_effect = ValueError("invalid field")
        with self.assertRaisesRegex(ValueError, "invalid field"):
            self.drift.drift_field(None)


@unittest.skipUnless(shutil.which("helm") and shutil.which("kubectl"), "helm and kubectl required")
class ReadinessTests(unittest.TestCase):
    def probes(self, yaml):
        deployment, = [
            doc for doc in re.split(r"^---\s*$", yaml, flags=re.MULTILINE)
            if re.search(r"^kind: Deployment$", doc, re.MULTILINE)
        ]
        probes = {}
        lines = deployment.splitlines()
        for i, line in enumerate(lines):
            name = line.strip().removesuffix(":")
            if name not in {"readinessProbe", "livenessProbe"}:
                continue
            indent = len(line) - len(line.lstrip())
            block = takewhile(lambda line: len(line) - len(line.lstrip()) > indent, lines[i + 1:])
            probes[name] = sorted(line.strip() for line in block)
        return probes

    def test_only_the_opted_in_readiness_path_changes(self):
        standards = ROOT / "platform/standards"
        helm = [
            "helm", "template", "sample-service", str(standards / "helm/app"),
            "-f", str(standards / "examples/sample-service/deploy/values.yaml"),
            "--set", "image.repository=sample-service,image.tag=local",
        ]
        baseline = self.probes(subprocess.check_output(helm, text=True))
        overlay = self.probes(subprocess.check_output([*helm, "--post-renderer", str(RENDERER)], text=True))
        self.assertIn("path: /health", baseline["readinessProbe"])
        self.assertIn("path: /health", baseline["livenessProbe"])
        self.assertEqual(overlay["livenessProbe"], baseline["livenessProbe"])
        expected = ["path: /robots933456.txt" if line == "path: /health" else line for line in baseline["readinessProbe"]]
        self.assertEqual(overlay["readinessProbe"], sorted(expected))

    def test_invalid_manifest_fails_without_rendering(self):
        result = subprocess.run([str(RENDERER)], input="invalid: [", capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(result.stdout)


if __name__ == "__main__":
    unittest.main()
