import hashlib
import http.client
import json
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
import uuid
from contextlib import contextmanager
from dataclasses import asdict, replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from jsonschema import Draft7Validator

from portal_wave import LOOPBACK, TARGET_HEADER, Plan, Route, Target, freeze, make_router, rehearse, sample


HERE = Path(__file__).resolve().parent


def fixture(run_token, adapter):
    class Handler(BaseHTTPRequestHandler):
        def respond(self):
            if self.path == "/identity":
                payload = self.server.identity
            else:
                payload = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                payload = payload or f"{adapter}:{self.path}".encode()
            self.send_response(503 if self.path == "/health" and self.server.degraded else 200)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Set-Cookie", "first=1")
            self.send_header("Set-Cookie", "second=2")
            self.send_header(TARGET_HEADER, "untrusted-upstream-header")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(payload)

        do_GET = do_HEAD = do_POST = respond

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer((LOOPBACK, 0), Handler)
    server.identity = f"{run_token}:{adapter}".encode()
    server.degraded = False
    return server


@contextmanager
def running(server, name):
    with server:
        worker = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, name=name)
        worker.start()
        try:
            yield server.server_port
        finally:
            server.shutdown()
            worker.join()


class PortalWaveTest(unittest.TestCase):
    @contextmanager
    def wave(self):
        token = f"FAKE_{uuid.uuid4().hex}"
        java, candidate = fixture(token, "java"), fixture(token, "serverless")
        logs = []
        with tempfile.TemporaryDirectory(prefix=token) as state:
            with running(java, f"{token}:java") as java_port, running(candidate, f"{token}:serverless") as lambda_port:
                with socket.socket() as port:
                    port.bind((LOOPBACK, 0))
                    router_port = port.getsockname()[1]
                plan = Plan(token, router_port, Target(java_port, f"{token}:java", "/identity"),
                            Target(lambda_port, f"{token}:serverless", "/identity"), "/health",
                            window_ms=300, interval_ms=100, timeout_ms=80, max_error_rate=0, max_p95_ms=70)
                root = Path(state)
                route = Route(plan, root)
                route.initialize()
                self.assertEqual(route.directory.name, token)
                with running(make_router(route, logs.append), f"{token}:router"):
                    yield route, java, candidate, logs
        self.assertFalse(root.exists())
        for port_number in (java_port, lambda_port, router_port):
            with self.assertRaises(ConnectionRefusedError):
                socket.create_connection((LOOPBACK, port_number), timeout=0.5)
        self.assertFalse(any(worker.name.startswith(token) for worker in threading.enumerate()))

    def assert_rollback(self, route, logs, result, reason):
        schema = json.loads((HERE / "evidence/closeout.schema.json").read_text())
        Draft7Validator({"$ref": "#/definitions/rehearsal", "definitions": schema["definitions"]}).validate(result)
        self.assertEqual(result["run_token"], route.plan.run_token)
        self.assertEqual(result["rollback_reason"], reason)
        self.assertEqual(result["frozen_sha256"], hashlib.sha256(route.frozen.read_bytes()).hexdigest())
        self.assertEqual(result["prior_restored"]["target_identity"], route.plan.java.identity)
        self.assertEqual(result["prior_restored"]["status"], "passed")
        self.assertEqual(result["recovered"]["observed_targets"], [route.plan.java.identity])
        self.assertEqual(result["recovered"]["errors"], 0)
        self.assertEqual(result["recovered"]["status"], "passed")
        self.assertEqual(result["recovery_status"], "passed")
        self.assertEqual(route.selected(), "java")
        self.assertGreaterEqual(result["rollback_elapsed_ms"], route.plan.window_ms)
        self.assertGreaterEqual(result["elapsed_ms"], result["rollback_elapsed_ms"])
        self.assertEqual({entry["run_token"] for entry in logs}, {route.plan.run_token})
        names = [entry["adapter"] for entry in logs]
        self.assertEqual(names[0], "java")
        self.assertIn("serverless", names)
        self.assertEqual(names[-1], "java")

    def test_gate_trip_restores_java(self):
        with self.wave() as (route, _, candidate, logs):
            freeze(route)
            candidate.degraded = True
            result = rehearse(route)
            self.assertEqual(result["candidate"]["status"], "failed")
            self.assertEqual(result["candidate"]["errors"], 3)
            self.assertEqual(result["candidate"]["estimated_downtime_ms"], route.plan.window_ms)
            self.assertEqual(result["candidate"]["observed_targets"], [route.plan.serverless.identity])
            self.assert_rollback(route, logs, result, "gate-trip")

    def test_healthy_serverless_runs_rollback_drill(self):
        with self.wave() as (route, _, _, logs):
            frozen = freeze(route)
            self.assertEqual(frozen["selected_adapter"], "serverless")
            self.assertEqual(frozen["plan"], asdict(route.plan))
            self.assertEqual(frozen["baseline"]["errors"], 0)
            self.assertIsNotNone(frozen["baseline"]["p95_ms"])
            with self.assertRaisesRegex(ValueError, "already frozen"):
                freeze(route)
            result = rehearse(route)
            self.assertEqual(result["candidate"]["status"], "passed")
            self.assertEqual(result["candidate"]["estimated_downtime_ms"], 0)
            self.assertEqual(result["prior_restored"]["body_sha256"], frozen["prior"]["body_sha256"])
            self.assert_rollback(route, logs, result, "planned-drill")

    def test_unhealthy_baseline_and_revised_plan_cannot_switch(self):
        with self.wave() as (route, java, _, _):
            java.degraded = True
            self.assertEqual(freeze(route)["baseline"]["status"], "failed")
            with self.assertRaisesRegex(ValueError, "baseline must pass"):
                rehearse(route)
            changed = Route(replace(route.plan, max_p95_ms=10), route.directory.parent)
            with self.assertRaisesRegex(ValueError, "differs from the frozen"):
                rehearse(changed)
            self.assertEqual(route.selected(), "java")

    def test_changed_upstream_identity_trips_gate(self):
        with self.wave() as (route, _, candidate, logs):
            freeze(route)
            candidate.identity = b"changed"
            result = rehearse(route)
            self.assertEqual(result["candidate"]["status"], "passed")
            self.assertEqual(result["candidate_endpoint"]["status"], "failed")
            self.assert_rollback(route, logs, result, "gate-trip")

    def test_p95_threshold_and_wrong_target_trip_health_gate(self):
        with self.wave() as (route, _, _, _):
            result = sample(replace(route.plan, max_p95_ms=0.000001), "java")
            self.assertEqual(result["errors"], 0)
            self.assertEqual(result["status"], "failed")
            result = sample(route.plan, "serverless")
            self.assertEqual(result["observed_targets"], [route.plan.java.identity])
            self.assertEqual(result["errors"], result["samples"])
            self.assertEqual(result["status"], "failed")

    def test_cli_switch_and_rollback_only_forward_to_loopback(self):
        with self.wave() as (route, _, _, _):
            plan = route.directory / "test-plan.json"
            plan.write_text(json.dumps(asdict(route.plan)))

            def command(action):
                proc = subprocess.run([sys.executable, str(HERE / "portal_wave.py"), action, "--plan", str(plan),
                                       "--state-root", str(route.directory.parent)], capture_output=True, text=True)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                return json.loads(proc.stdout)

            self.assertEqual(command("freeze")["baseline"]["status"], "passed")
            self.assertEqual(command("switch")["adapter"], "serverless")
            connection = http.client.HTTPConnection(LOOPBACK, route.plan.router_port, timeout=1)
            try:
                connection.request("POST", "/sample?key=value", body=b"synthetic", headers={"Host": "example.invalid"})
                response = connection.getresponse()
                self.assertEqual(response.read(), b"synthetic")
                self.assertEqual(response.getheader(TARGET_HEADER), route.plan.serverless.identity)
                self.assertEqual([value for key, value in response.getheaders() if key == "Set-Cookie"], ["first=1", "second=2"])
                connection.request("GET", "http://example.invalid/blocked")
                self.assertEqual(connection.getresponse().status, 400)
            finally:
                connection.close()
            self.assertEqual(command("rollback")["adapter"], "java")
            self.assertEqual(route.selected(), "java")
            for source in (replace(route.plan.java, port="example.invalid"),
                           replace(route.plan.java, identity_path="http://example.invalid/health")):
                with self.assertRaises(ValueError):
                    replace(route.plan, java=source)


class CloseoutSchemaTest(unittest.TestCase):
    def test_observed_closeout_matches_frozen_plan_and_cleanup(self):
        directory = HERE / "evidence"
        schema = json.loads((directory / "closeout.schema.json").read_text())
        closeout = json.loads((directory / "CMG_20261128.closeout.json").read_text())
        Draft7Validator(schema).validate(closeout)
        frozen_raw = (directory / closeout["provenance"]["frozen_file"]).read_bytes()
        frozen = json.loads(frozen_raw)
        portal = closeout["workloads"]["portal"]
        plan, rehearsal = frozen["plan"], portal["rehearsal"]
        self.assertEqual(rehearsal["frozen_sha256"], hashlib.sha256(frozen_raw).hexdigest())
        self.assertEqual(rehearsal["prior_restored"], frozen["prior"])
        for window in (frozen["baseline"], rehearsal["candidate"], rehearsal["recovered"]):
            self.assertEqual(window["samples"], plan["window_ms"] // plan["interval_ms"])
            self.assertLessEqual(window["error_rate"], plan["max_error_rate"])
            self.assertLessEqual(window["p95_ms"], plan["max_p95_ms"])
            self.assertEqual(window["estimated_downtime_ms"], window["errors"] * plan["interval_ms"])
        identities = closeout["provenance"]["image_ids"]
        self.assertEqual(plan["java"]["identity"], "java@" + identities["java"])
        self.assertEqual(plan["serverless"]["identity"], "serverless@" + identities["gateway"])
        self.assertEqual(closeout["cleanup_verification"]["run_token"], plan["run_token"])
        self.assertEqual(plan["run_token"], closeout["run_token"])
        self.assertEqual(closeout["workloads"]["kubernetes"]["gates"]["portable_replay"]["status"], "unrun")

    def test_simulated_example_does_not_claim_observation(self):
        schema = json.loads((HERE / "evidence/closeout.schema.json").read_text())
        example = json.loads((HERE / "evidence/simulated-s5.json").read_text())
        Draft7Validator.check_schema(schema)
        validator = Draft7Validator(schema)
        validator.validate(example)
        gates = example["workloads"]["portal"]["gates"]
        gates["candidate_health"] = {"status": "passed", "observed": True, "evidence": "fake.json"}
        self.assertFalse(validator.is_valid(example))
        example["mode"] = "observed-local"
        gates["candidate_health"]["observed"] = False
        self.assertFalse(validator.is_valid(example))
        gates["candidate_health"] = {"status": "unrun", "observed": False, "reason": "Pending S4."}
        example["workloads"]["portal"]["disposition"] = "local-drill-complete"
        self.assertFalse(validator.is_valid(example))


if __name__ == "__main__":
    unittest.main()
