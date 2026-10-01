"""verify.sh gates from a checkout that never ran arm.sh.

kubectl, helm and curl are stubbed with canned cluster answers; jq, date,
python3 and the real verify.sh / lib.sh / faults.yaml run unchanged.
"""

import json
import os
import subprocess
import tempfile
import textwrap
import time
import unittest
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).parent
TENANT = "oncall-before"
NS = f"otterworks-{TENANT}"

STORM = [
    ("EdgeErrorRatioHigh", "web-edge"),
    ("EdgeLatencyP95High", "web-edge"),
    ("GatewayErrorRatioHigh", "api-gateway"),
    ("GatewayLatencyP95High", "api-gateway"),
    ("FolderListLatencyHigh", "document-service"),
    ("DocumentServiceErrorRateHigh", "document-service"),
    ("DbPoolSaturated", "document-service"),
    ("DbStatementTimeouts", "document-service"),
    ("FolderDigestBacklogGrowing", "document-service"),
    ("PostgresCPUThrottled", "postgres"),
    ("PostgresActiveConnectionsHigh", "postgres"),
    ("PostgresLongRunningQueries", "postgres"),
]

KUBECTL = """\
#!/usr/bin/env python3
import os, pathlib, sys, time
args = sys.argv[1:]
if "port-forward" in args:
    lport = args[args.index("port-forward") + 2].split(":")[0]
    pathlib.Path(os.environ["STUB_DIR"], f"pf-{lport}").touch()
    time.sleep(300)
    sys.exit(0)
if args[:2] == ["get", "ns"]:
    sys.exit(0)
if "get" in args and "job" in args:
    import json
    fx = json.load(open(os.environ["STUB_FIXTURE"]))
    path = next(a for a in args if a.startswith("jsonpath="))
    print(fx.get("k6", {}).get(path.split("{.status.")[1].rstrip("}"), ""), end="")
    sys.exit(0)
sys.exit(f"kubectl stub: unexpected {args}")
"""

HELM = """\
#!/usr/bin/env python3
import json, os, sys
fx = json.load(open(os.environ["STUB_FIXTURE"]))
args = sys.argv[1:]
if "history" in args:
    print(json.dumps(fx["history"]))
elif "get" in args and "values" in args:
    rev = str(fx["history"][-1]["revision"])
    if "--revision" in args:
        rev = args[args.index("--revision") + 1]
    print(json.dumps(fx["values"][rev]))
else:
    sys.exit(f"helm stub: unexpected {args}")
"""

CURL = """\
#!/usr/bin/env python3
import json, os, pathlib, sys, urllib.parse
fx = json.load(open(os.environ["STUB_FIXTURE"]))
args = sys.argv[1:]
url = next(a for a in args if a.startswith("http"))
data = dict(a.split("=", 1) for i, a in enumerate(args) if i and args[i - 1] == "--data-urlencode")
parts = urllib.parse.urlparse(url)
port = str(parts.port)
if not pathlib.Path(os.environ["STUB_DIR"], f"pf-{port}").exists():
    sys.exit(7)
path = parts.path
def vector(samples):
    print(json.dumps({"status": "success", "data": {"resultType": "vector", "result": samples}}))
if path.endswith("/-/ready"):
    pass
elif path == "/api/v1/query":
    q, at = data["query"], float(data.get("time", "inf"))
    if q.startswith("ALERTS{"):
        vector([{"metric": m, "value": [0, "1"]} for m in fx["firing"]])
    elif q == 'sum(alertmanager_notifications_total{integration="webhook"})':
        vector([{"metric": {}, "value": [at, "6" if at > fx["deploy_epoch"] else "5"]}])
    elif q.startswith("histogram_quantile(0.95"):
        vector([{"metric": {}, "value": [0, "0.24"]}])
    elif q.startswith("sum(rate(http_request_duration_seconds_count"):
        vector([{"metric": {}, "value": [0, "6.1"]}])
    else:
        vector([])
elif path == "/api/v2/alerts/groups":
    print(json.dumps(fx["groups"]))
elif path == "/api/v2/silences":
    print(json.dumps(fx.get("silences", [])))
elif path == "/api/v2/status":
    print(json.dumps({"config": {"original": fx["am_config"]}}))
else:
    sys.exit(f"curl stub: unexpected {url}")
"""

AM_CONFIG = textwrap.dedent(
    """\
    route:
      receiver: default
      routes:
        - receiver: oncall-devin
          group_by: [namespace, oncall_group]
          group_wait: 3m
          group_interval: 6h
    """
)


def helm_time(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, UTC).strftime("%Y-%m-%dT%H:%M:%S.123456789+00:00")


def iso(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class VerifyHarness(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.bin = self.dir / "bin"
        self.bin.mkdir()
        for name, body in {"kubectl": KUBECTL, "helm": HELM, "curl": CURL}.items():
            stub = self.bin / name
            stub.write_text(body)
            stub.chmod(0o755)
        self.state = self.dir / "state"
        self.reports = self.dir / "reports"
        now = int(time.time())
        self.deploy = now - 900
        self.run_id = str(self.deploy - 5)

    def tearDown(self):
        self.tmp.cleanup()

    def fixture(self, run: str) -> dict:
        labels = {"page": "oncall", "oncall_group": "folder-storm", "namespace": NS}
        alert_labels = dict(labels, oncall_run=run) if run else labels
        on = {"folderDigest": {"enabled": True}}
        if run:
            on["monitoring"] = {"rules": {"extraLabels": {"oncall_run": run}}}
        return {
            "deploy_epoch": self.deploy,
            "history": [
                {"revision": 1, "updated": helm_time(self.deploy - 7200), "status": "superseded"},
                {"revision": 2, "updated": helm_time(self.deploy - 3600), "status": "superseded"},
                {"revision": 3, "updated": helm_time(self.deploy), "status": "superseded"},
                {"revision": 4, "updated": helm_time(self.deploy + 120), "status": "deployed"},
            ],
            "values": {
                "1": {},
                "2": {"folderDigest": {"enabled": False}},
                "3": on,
                "4": on,
            },
            "firing": [
                {"alertname": n, "service": s, "namespace": NS, "page": "oncall"} for n, s in STORM
            ],
            "groups": [
                {
                    "receiver": {"name": "oncall-devin"},
                    "labels": labels,
                    "alerts": [
                        {"labels": alert_labels, "startsAt": iso(self.deploy + 78)},
                        {"labels": alert_labels, "startsAt": iso(self.deploy + 140)},
                    ],
                }
            ],
            "am_config": AM_CONFIG,
        }

    def verify(
        self, fixture: dict, tenant: str = TENANT, expect: str = "before"
    ) -> subprocess.CompletedProcess:
        path = self.dir / "fixture.json"
        path.write_text(json.dumps(fixture))
        env = dict(
            os.environ,
            PATH=f"{self.bin}:{os.environ['PATH']}",
            KUBERNETES_SERVICE_HOST="stub",
            STUB_DIR=str(self.dir),
            STUB_FIXTURE=str(path),
            ONCALL_STATE_DIR=str(self.state),
            ONCALL_REPORT_DIR=str(self.reports),
            ONCALL_PROM_PORT="29590",
            ONCALL_AM_PORT="29593",
        )
        return subprocess.run(
            [str(HERE / "verify.sh"), tenant, expect],
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )

    def report(self, tenant: str = TENANT, expect: str = "before") -> dict:
        (report,) = self.reports.glob(f"{tenant}-{expect}-*.json")
        return json.loads(report.read_text())


class VerifyWithoutStateTests(VerifyHarness):
    def test_before_gate_reads_the_deploy_from_helm_without_state(self):
        self.assertFalse(self.state.exists())
        result = self.verify(self.fixture(self.run_id))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"INFO config deploy from helm: at {iso(self.deploy)}", result.stdout)
        self.assertIn(f"PASS alerts from this arm (oncall_run={self.run_id})", result.stdout)
        self.assertIn("PASS first storm alert 78s after the config deploy", result.stdout)
        report = self.report()
        self.assertTrue(report["ok"])
        self.assertEqual(report["measures"]["deploy_record_source"], "helm")
        self.assertEqual(report["measures"]["oncall_run"], self.run_id)
        cached = json.loads((self.state / f"{TENANT}.json").read_text())["steps"]["deploy"]
        self.assertEqual(cached["at"], iso(self.deploy))
        self.assertEqual(cached["revision"], 3)
        self.assertEqual(cached["oncall_run"], self.run_id)
        self.assertEqual(cached["source"], "helm")

    def test_stale_state_from_an_older_arm_falls_back_to_helm(self):
        self.state.mkdir()
        stale = {"steps": {"deploy": {"at": iso(self.deploy - 3600), "oncall_run": "1"}}}
        (self.state / f"{TENANT}.json").write_text(json.dumps(stale))
        result = self.verify(self.fixture(self.run_id))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("INFO config deploy from helm", result.stdout)

    def test_before_gate_stays_red_without_an_oncall_run_anywhere(self):
        result = self.verify(self.fixture(""))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("INFO config deploy from none", result.stdout)
        self.assertIn("FAIL alerts from this arm (oncall_run=unset)", result.stdout)
        self.assertFalse(self.report()["ok"])


AFTER = "oncall-after"
AFTER_NS = f"otterworks-{AFTER}"


class VerifyAfterTests(VerifyHarness):
    def after_fixture(self, groups: list | None = None, silences: list | None = None) -> dict:
        fx = self.fixture(self.run_id)
        fx["firing"] = []
        fx["groups"] = groups or []
        fx["silences"] = silences or []
        fx["k6"] = {"active": "1", "startTime": iso(int(time.time()) - 600)}
        return fx

    def verify_after(self, fx: dict) -> subprocess.CompletedProcess:
        return self.verify(fx, AFTER, "after")

    def test_after_gate_green_with_no_page_of_its_own(self):
        result = self.verify_after(self.after_fixture())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(
            f"PASS Alertmanager groups for oncall-devin in {AFTER_NS}: 0 (need 0)", result.stdout
        )
        self.assertIn(f"PASS harness silences still active on {AFTER_NS}: 0", result.stdout)
        measures = self.report(AFTER, "after")["measures"]
        self.assertEqual(measures["devin_groups"], 0)
        self.assertEqual(measures["harness_silences"], 0)

    def test_after_gate_red_when_the_fixed_tenant_opened_an_oncall_devin_group(self):
        labels = {"page": "oncall", "oncall_group": "folder-storm", "namespace": AFTER_NS}
        group = {
            "receiver": {"name": "oncall-devin"},
            "labels": labels,
            "alerts": [{"labels": labels, "startsAt": iso(self.deploy + 150)}],
        }
        result = self.verify_after(self.after_fixture(groups=[group]))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            f"FAIL Alertmanager groups for oncall-devin in {AFTER_NS}: 1 (need 0)", result.stdout
        )
        self.assertFalse(self.report(AFTER, "after")["ok"])

    def test_after_gate_red_while_the_arm_silence_is_still_active(self):
        silence = {"id": "s1", "createdBy": "oncall-harness", "status": {"state": "active"}}
        expired = {"id": "s0", "createdBy": "oncall-harness", "status": {"state": "expired"}}
        other = {"id": "s2", "createdBy": "someone", "status": {"state": "active"}}
        result = self.verify_after(self.after_fixture(silences=[silence, expired, other]))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(f"FAIL harness silences still active on {AFTER_NS}: 1", result.stdout)


if __name__ == "__main__":
    unittest.main()
