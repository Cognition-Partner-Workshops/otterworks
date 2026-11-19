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
        self.assertEqual(render("--set", "mongodb.enabled=false", "--set", "sync.enabled=false"), [])

    def test_default(self):
        objects = render()
        self.assertEqual({obj["kind"] for obj in objects},
                         {"Secret", "ConfigMap", "StatefulSet", "Deployment", "Service", "NetworkPolicy"})
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
        objects = render("--set", "mongodb.enabled=false", "--set", "sync.enabled=false",
                         "--set", "observability.enabled=true")
        self.assertEqual(len(objects), 2)
        rules = next(obj for obj in objects if obj["kind"] == "PrometheusRule")
        source = yaml.safe_load((ROOT / "observability/prometheus/odl_rules.yml").read_text())
        self.assertEqual(rules["spec"], source)
        cm = next(obj for obj in objects if obj["kind"] == "ConfigMap")
        self.assertEqual(cm["metadata"]["labels"]["grafana_dashboard"], "1")
        self.assertEqual(json.loads(cm["data"]["odl-overview.json"]),
                         json.loads((ROOT / "observability/grafana/dashboards/odl-overview.json").read_text()))

    def test_sync_deployment_and_service(self):
        objects = render("--set", "mongodb.enabled=false", "--set", "sync.image=example/odl:test",
                         "--set", "sync.intervalSeconds=600")
        self.assertEqual({obj["kind"] for obj in objects}, {"Deployment", "Service"})
        deployment = next(obj for obj in objects if obj["kind"] == "Deployment")
        service = next(obj for obj in objects if obj["kind"] == "Service")
        for obj in objects:
            self.assertEqual(obj["metadata"]["name"], "operational-data-layer")
            self.assertEqual(obj["metadata"]["labels"]["run_token"], "odl-1795112287")
        self.assertEqual(deployment["metadata"]["labels"]["otterworks.io/scale-with-tenant"], "true")
        self.assertEqual(deployment["spec"]["replicas"], 1)
        self.assertEqual(deployment["spec"]["strategy"]["type"], "Recreate")
        pod = deployment["spec"]["template"]
        self.assertEqual(pod["metadata"]["labels"]["run_token"], "odl-1795112287")
        self.assertTrue(pod["spec"]["securityContext"]["runAsNonRoot"])
        self.assertFalse(pod["spec"]["automountServiceAccountToken"])
        container = pod["spec"]["containers"][0]
        self.assertEqual(container["image"], "example/odl:test")
        self.assertEqual(container["command"], ["python", "-m", "odl_sync.api"])
        self.assertEqual(container["ports"], [{"name": "http", "containerPort": 8098}])
        for name in ("startupProbe", "readinessProbe", "livenessProbe"):
            self.assertEqual(container[name]["httpGet"], {"path": "/health", "port": "http"})
        self.assertEqual(container["resources"], {
            "requests": {"cpu": "250m", "memory": "768Mi"},
            "limits": {"cpu": "1", "memory": "3Gi"},
        })
        env = {item["name"]: item for item in container["env"]}
        for name, value in {"DB2_HOST": "db2-archive", "DB2_PORT": "50000", "DB2_DATABASE": "ODL",
                            "ORACLE_DSN": "oracle:1521/FREEPDB1", "MONGO_HOST": "operational-data-layer-mongo",
                            "MONGO_PORT": "27017", "MONGO_DATABASE": "odl", "MONGO_AUTH_SOURCE": "odl",
                            "ODL_HOST": "0.0.0.0", "ODL_PORT": "8098", "ODL_SYNC_INTERVAL_SECONDS": "600"}.items():
            self.assertEqual(env.pop(name), {"name": name, "value": value})
        for name, secret, key in (
            ("JWT_SECRET", "api-gateway-secrets", "JWT_SECRET"),
            ("DB2_USER", "db2-archive-credentials", "DB2_USER"),
            ("DB2_PASSWORD", "db2-archive-credentials", "DB2_PASSWORD"),
            ("ORACLE_USER", "odl-oracle", "ORACLE_USER"),
            ("ORACLE_PASSWORD", "odl-oracle", "ORACLE_PASSWORD"),
            ("PGHOST", "odl-postgres", "DB_HOST"), ("PGPORT", "odl-postgres", "DB_PORT"),
            ("PGDATABASE", "odl-postgres", "DB_NAME"), ("PGUSER", "odl-postgres", "DB_USER"),
            ("PGPASSWORD", "odl-postgres", "DB_PASSWORD"),
            ("MONGO_USER", "operational-data-layer-mongo", "username"),
            ("MONGO_PASSWORD", "operational-data-layer-mongo", "password"),
        ):
            self.assertEqual(env.pop(name), {"name": name, "valueFrom": {"secretKeyRef": {"name": secret, "key": key}}})
        self.assertEqual(env, {})
        self.assertEqual(service["spec"]["type"], "ClusterIP")
        self.assertEqual(service["spec"]["selector"], deployment["spec"]["selector"]["matchLabels"])
        self.assertEqual(service["spec"]["ports"], [{"name": "http", "port": 8098, "targetPort": "http"}])
        with self.assertRaisesRegex(ValueError, "sync.image is required"):
            render("--set", "sync.image=")

    def test_sync_disabled(self):
        objects = render("--set", "sync.enabled=false", "--api-versions", "monitoring.coreos.com/v1")
        self.assertFalse(any(obj["kind"] in ("Deployment", "ServiceMonitor") for obj in objects))
        self.assertFalse(any(obj["metadata"]["name"] == "operational-data-layer" for obj in objects))

    def test_sync_monitor(self):
        objects = render("--api-versions", "monitoring.coreos.com/v1", "--set",
                         "sync.monitoring.additionalLabels.release=prometheus")
        monitor = next(obj for obj in objects if obj["kind"] == "ServiceMonitor")
        service = next(obj for obj in objects if obj["kind"] == "Service"
                       and obj["metadata"]["name"] == "operational-data-layer")
        self.assertEqual(monitor["metadata"]["labels"]["release"], "prometheus")
        self.assertEqual(monitor["metadata"]["labels"]["run_token"], "odl-1795112287")
        for key, value in monitor["spec"]["selector"]["matchLabels"].items():
            self.assertEqual(service["metadata"]["labels"][key], value)
        self.assertEqual(monitor["spec"]["endpoints"], [{"port": "http", "path": "/metrics", "interval": "30s"}])
        objects = render("--api-versions", "monitoring.coreos.com/v1", "--set", "sync.monitoring.enabled=false")
        self.assertFalse(any(obj["kind"] == "ServiceMonitor" for obj in objects))


if __name__ == "__main__":
    unittest.main()
