import json
import subprocess
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[4]
CHART = ROOT / "services/operational-data-layer/deploy"


def render(*args):
    result = subprocess.run(["helm", "template", "operational-data-layer", str(CHART),
                             "-n", "otterworks-test", *args], capture_output=True, text=True)
    if result.returncode:
        raise ValueError(result.stderr)
    return [obj for obj in yaml.safe_load_all(result.stdout) if obj]


class ChartTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(render("--set", "mongodb.enabled=false"), [])

    def test_default(self):
        objects = render()
        self.assertEqual({obj["kind"] for obj in objects},
                         {"Secret", "ConfigMap", "StatefulSet", "Service", "NetworkPolicy"})
        for obj in objects:
            self.assertEqual(obj["metadata"]["labels"]["run_token"], "odl-1795112287")
        sts = next(obj for obj in objects if obj["kind"] == "StatefulSet")
        self.assertEqual(sts["metadata"]["labels"]["otterworks.io/scale-with-tenant"], "true")
        self.assertIn("emptyDir", sts["spec"]["template"]["spec"]["volumes"][1])
        container = sts["spec"]["template"]["spec"]["containers"][0]
        self.assertIn("--auth", container["args"])
        for key in ("startupProbe", "readinessProbe", "livenessProbe"):
            self.assertIn("process.env.ODL_MONGO_PASSWORD", container[key]["exec"]["command"][-1])
        policy = next(obj for obj in objects if obj["kind"] == "NetworkPolicy")
        self.assertEqual(policy["spec"]["ingress"][0]["from"], [{"podSelector": {}}])

    def test_existing_claim_and_invalid_username(self):
        objects = render("--set", "persistence.existingClaim=terraform-volume")
        sts = next(obj for obj in objects if obj["kind"] == "StatefulSet")
        self.assertEqual(sts["spec"]["template"]["spec"]["volumes"][1]["persistentVolumeClaim"],
                         {"claimName": "terraform-volume"})
        self.assertFalse(any(obj["kind"] in ("PersistentVolume", "PersistentVolumeClaim") for obj in objects))
        with self.assertRaisesRegex(ValueError, "mongodb.username is required"):
            render("--set", "mongodb.username=")

    def test_observability_matches_sources(self):
        objects = render("--set", "mongodb.enabled=false", "--set", "observability.enabled=true")
        self.assertEqual(len(objects), 2)
        rules = next(obj for obj in objects if obj["kind"] == "PrometheusRule")
        source = yaml.safe_load((ROOT / "observability/prometheus/odl_rules.yml").read_text())
        self.assertEqual(rules["spec"], source)
        cm = next(obj for obj in objects if obj["kind"] == "ConfigMap")
        self.assertEqual(cm["metadata"]["labels"]["grafana_dashboard"], "1")
        self.assertEqual(json.loads(cm["data"]["odl-overview.json"]),
                         json.loads((ROOT / "observability/grafana/dashboards/odl-overview.json").read_text()))


if __name__ == "__main__":
    unittest.main()
