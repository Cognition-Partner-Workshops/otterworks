import base64
import importlib.util
import io
import json
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import yaml

ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


seed = load("seed", "infrastructure/k8s/odl-mocks/seed.py")
confluence = load("confluence_seed", "infrastructure/k8s/odl-mocks/confluence-seed.py")
relay = load("relay", "infrastructure/k8s/odl-mocks/relay.py")
routing = load("routing", "scripts/odl/route-alerts.py")


class NetworkPolicyTests(unittest.TestCase):
    def test_only_controller_and_monitoring_namespaces(self):
        policies = list(yaml.safe_load_all(
            (ROOT / "infrastructure/k8s/odl-mocks/networkpolicy.yaml").read_text()))
        self.assertEqual({p["metadata"]["name"] for p in policies}, {"jira", "pagerduty", "confluence", "jira-devin-relay"})
        for policy in policies:
            if policy["metadata"]["name"] == "jira-devin-relay":
                self.assertEqual(policy["spec"]["podSelector"], {"matchLabels": {"app": "jira-devin-relay"}})
                self.assertEqual(policy["spec"]["ingress"], [{"from": [{"podSelector": {"matchLabels": {"app": "jira"}}}],
                                                            "ports": [{"protocol": "TCP", "port": 8080}]}])
                self.assertEqual(policy["metadata"]["namespace"], "odl-mocks")
                self.assertEqual(policy["metadata"]["labels"]["run_token"], "odl-1795112287")
                continue
            self.assertEqual(policy["metadata"]["namespace"], "odl-mocks")
            self.assertEqual(policy["metadata"]["labels"]["run_token"], "odl-1795112287")
            self.assertEqual(policy["spec"]["podSelector"],
                             {"matchLabels": {"app": policy["metadata"]["name"]}})
            self.assertEqual(policy["spec"]["ingress"], [{"from": [
                {"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": ns}}}
                for ns in ("ingress-nginx", "monitoring")], "ports": [{"protocol": "TCP", "port": 8080}]}])


class DeployTests(unittest.TestCase):
    def run_credentials(self, scope, existing=True, create_status=0):
        script = (ROOT / "scripts/odl/deploy-mocks.sh").read_text()
        program = script.split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]

        def run(args, **kwargs):
            if "get" in args:
                return subprocess.CompletedProcess(args, 0, stdout="{}" if existing else "")
            if args[0] == "openssl":
                return subprocess.CompletedProcess(args, 0, stdout="test-hash")
            return subprocess.CompletedProcess(args, create_status)

        with patch.object(sys, "argv", ["-", scope]), patch.object(subprocess, "run", side_effect=run) as calls:
            exec(compile(program, "deploy-mocks credentials", "exec"), {})
        return calls.call_args_list

    def test_existing_secrets_are_not_written(self):
        calls = self.run_credentials("all")
        self.assertEqual([call.args[0][5] for call in calls], [
            "jira-devin-webhook", "jira-mock-basic-auth", "pagerduty-mock-basic-auth",
            "confluence-mock-basic-auth"])
        self.assertTrue(all("get" in call.args[0] for call in calls))

    def test_confluence_scope_does_not_access_jira_or_relay(self):
        calls = self.run_credentials("confluence")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].args[0][5], "confluence-mock-basic-auth")
        with redirect_stdout(io.StringIO()):
            calls = self.run_credentials("confluence", existing=False)
        created = [json.loads(call.kwargs["input"]) for call in calls if "create" in call.args[0]]
        self.assertEqual([obj["metadata"]["name"] for obj in created], ["confluence-mock-basic-auth"])

    def test_secret_creation_failure(self):
        with self.assertRaises(SystemExit):
            self.run_credentials("confluence", existing=False, create_status=1)


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

    def test_webhook_is_registered_once_and_reregistered_after_reset(self):
        hook = {"id": 7, **seed.WEBHOOK}
        with patch.object(seed, "request", side_effect=[[], hook, [hook], [], {**hook, "id": 1}]) as call:
            with redirect_stdout(io.StringIO()) as output:
                self.assertEqual([seed.reconcile_webhook() for _ in range(3)], [7, 7, 1])
            self.assertEqual([c.args for c in call.call_args_list if len(c.args) == 2],
                             [(seed.WEBHOOK_PATH, seed.WEBHOOK)] * 2)
            self.assertEqual(output.getvalue().splitlines(), [
                "registered Devin webhook 7", "registered Devin webhook 1"])


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


class RelayTests(unittest.TestCase):
    def make_gate(self):
        state = relay.ConfigMapState.__new__(relay.ConfigMapState)
        persisted = {}

        def configmap(method="GET", body=None):
            if method == "PATCH":
                for key, value in json.loads(body)["data"].items():
                    if value is None:
                        persisted.pop(key, None)
                    else:
                        persisted[key] = value
            return {"data": persisted.copy()}

        state.request = configmap
        return relay.LabelGate(state)

    def test_forward_only_labelled_creations_and_supported_events(self):
        gate = self.make_gate()
        issue = {"key": "ENG-7", "fields": {"labels": ["not-devin"]}}
        created = {"webhookEvent": "jira:issue_created", "issue": issue}
        self.assertEqual(gate.skip_reason(created, "ENG-7"), "devin_label_absent")
        issue["fields"]["labels"].append("devin")
        self.assertIsNone(gate.skip_reason(created, "ENG-7"))
        self.assertEqual(gate.skip_reason({**created, "webhookEvent": "comment_created"}, "ENG-7"),
                         "unsupported_event")
        self.assertEqual(gate.skip_reason({**created, "webhookEvent": "jira:issue_updated"}, "ENG-7"),
                         "devin_label_already_seen")

    def test_explicit_changelog_does_not_fall_back_to_snapshot(self):
        for field, old, new, reason in (
            ("labels", "other, devin", "devin", "changelog_did_not_add_devin"),
            ("labels", "other", "devin-secondary", "changelog_did_not_add_devin"),
            ("status", None, "devin", "changelog_did_not_add_devin"),
            ("labels", "not-devin, other", "other, devin", None),
            ("labels", None, "devin", None),
        ):
            with self.subTest(field=field, old=old, new=new):
                gate = self.make_gate()
                update = {"webhookEvent": "jira:issue_updated",
                          "issue": {"key": "ENG-7", "fields": {"labels": ["devin"]}},
                          "changelog": {"items": [{"field": field, "fromString": old, "toString": new}]}}
                self.assertEqual(gate.skip_reason(update, "ENG-7"), reason)

    def test_snapshot_transition_persists_and_clears_observed_removals(self):
        gate = self.make_gate()
        issue = {"key": "ENG-7", "fields": {"labels": ["devin"]}}
        update = {"webhookEvent": "jira:issue_updated", "issue": issue}
        self.assertIsNone(gate.skip_reason(update, "ENG-7"))
        gate = relay.LabelGate(gate.state)
        self.assertEqual(gate.skip_reason(update, "ENG-7"), "devin_label_already_seen")
        issue["fields"]["labels"] = []
        self.assertEqual(gate.skip_reason(update, "ENG-7"), "devin_label_absent")
        gate = relay.LabelGate(gate.state)
        issue["fields"]["labels"] = ["devin"]
        self.assertIsNone(gate.skip_reason(update, "ENG-7"))

    def start_server(self, handler):
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join)
        self.addCleanup(server.shutdown)
        return server, f"http://127.0.0.1:{server.server_port}"

    def test_delivery_bytes_secret_status_and_no_redirect(self):
        received = []

        class Upstream(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass

            def do_POST(self):
                received.append((self.path, self.headers.get("X-Webhook-Secret"),
                                 self.headers.get("Content-Type"),
                                 self.rfile.read(int(self.headers["Content-Length"]))))
                if self.path == "/redirect":
                    self.send_response(307)
                    self.send_header("Location", "/unexpected")
                else:
                    self.send_response(202)
                self.end_headers()

        _, upstream = self.start_server(Upstream)
        server, url = self.start_server(relay.Relay)
        server.upstream_url = upstream + "/accept"
        server.upstream_secret = "test-secret"
        server.gate = self.make_gate()
        body = (b'{ "issue": {"key": "ENG-7", "fields": {"labels": ["devin"]}},'
                b' "webhookEvent": "jira:issue_updated" }\n')
        delivery = Request(url + "/webhook", data=body, headers={"Content-Type": "application/json"})
        with redirect_stdout(io.StringIO()) as output:
            with urlopen(delivery, timeout=3) as response:
                self.assertEqual(response.status, 202)
            with urlopen(delivery, timeout=3) as response:
                self.assertEqual(response.status, 204)
            with urlopen(Request(url + "/webhook", data=b""), timeout=3) as response:
                self.assertEqual(response.status, 204)
            server.upstream_url = upstream + "/redirect"
            redirect_body = body.replace(b"ENG-7", b"ENG-8")
            with self.assertRaises(HTTPError) as rejected:
                urlopen(Request(url + "/webhook", data=redirect_body, headers=delivery.headers), timeout=3)
            self.assertEqual(rejected.exception.code, 502)
            rejected.exception.close()
        self.assertEqual(received, [("/accept", "test-secret", "application/json", body),
                                    ("/redirect", "test-secret", "application/json", redirect_body)])
        self.assertEqual(output.getvalue().splitlines(), [
            "issue=ENG-7 upstream_status=202", "issue=ENG-7 skip_reason=devin_label_already_seen",
            "issue=- skip_reason=invalid_payload", "issue=ENG-8 upstream_status=307"])


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
        return {"route": {"receiver": "null", "routes": [
                    {"receiver": "other", "matchers": ['namespace="other"'], "continue": True},
                    {"receiver": "devin-oncall", "matchers": ['page="devin"'], "group_wait": "5s"}]},
                "inhibit_rules": [{"equal": ["namespace"]}],
                "receivers": [{"name": "other", "webhook_configs": [{"url": "http://example.invalid"}]},
                              {"name": "devin-oncall", "webhook_configs": [
                                  {"url": "https://example.invalid", "send_resolved": False}],
                               "pagerduty_configs": [{"url": routing.EVENTS_URL,
                                   "routing_key_file": routing.KEY_FILE, "send_resolved": True,
                                   "severity": "error", "description": "preserve this"}]}]}

    def test_preserves_routes_other_receivers_and_is_idempotent(self):
        original = self.config()
        updated = routing.updated_config(original)
        self.assertEqual(updated, routing.updated_config(updated))
        self.assertEqual(original["receivers"], updated["receivers"][:-1])
        self.assertEqual(original["route"]["routes"], [r for r in updated["route"]["routes"]
                                                     if r["receiver"] != routing.RECEIVER])
        self.assertEqual(original["inhibit_rules"], updated["inhibit_rules"])
        receiver = updated["receivers"][-1]
        self.assertEqual(receiver["pagerduty_configs"], original["receivers"][-1]["pagerduty_configs"])
        self.assertTrue(receiver["pagerduty_configs"][0]["send_resolved"])
        self.assertEqual(receiver["webhook_configs"], [{"url_file": routing.URL_FILE, "send_resolved": False,
            "http_config": {"http_headers": {"X-Webhook-Secret": {"files": [routing.HEADER_FILE]}}}}])
        self.assertEqual(updated["route"]["routes"][1], {"receiver": routing.RECEIVER,
            "matchers": ['page="devin"', 'namespace="otterworks-odl"'], "group_wait": "5s"})
        self.assertNotIn("example.invalid", json.dumps(routing.structure(updated)))

    def test_corrects_existing_resolved_webhook_without_other_changes(self):
        expected = routing.updated_config(self.config())
        existing = routing.updated_config(self.config())
        existing["receivers"][-1]["webhook_configs"][0]["send_resolved"] = True
        corrected = routing.updated_config(existing)
        self.assertEqual(corrected, expected)
        self.assertTrue(existing["receivers"][-1]["webhook_configs"][0]["send_resolved"])
        self.assertFalse(corrected["receivers"][-1]["webhook_configs"][0]["send_resolved"])
        self.assertTrue(corrected["receivers"][-1]["pagerduty_configs"][0]["send_resolved"])
        self.assertEqual(routing.updated_config(corrected), corrected)

    def test_refuses_conflicting_or_partial_odl_routing(self):
        for part in ("route", "receiver", "position"):
            config = routing.updated_config(self.config())
            if part == "route":
                config["route"]["routes"][1]["matchers"] = ['page="devin"']
            elif part == "receiver":
                config["receivers"][-1]["webhook_configs"][0]["url_file"] = "/unexpected"
            else:
                config["route"]["routes"].reverse()
            with self.subTest(part=part), self.assertRaises(ValueError):
                routing.updated_config(config)
        config = self.config()
        config["receivers"][-1].pop("pagerduty_configs")
        with self.assertRaises(ValueError):
            routing.updated_config(config)

    def test_missing_or_ambiguous_receiver_rejected(self):
        for receivers in ([], [{"name": "devin-oncall", "webhook_configs": []}]):
            with self.assertRaises(ValueError):
                routing.updated_config({"receivers": receivers})


class WebhookSecretTests(unittest.TestCase):
    def values(self):
        return {"DEVIN_ALERT_WEBHOOK_URL": "https://example.invalid/test-hook",
                "DEVIN_ALERT_WEBHOOK_SECRET": "fixture-header"}

    def test_create_update_and_idempotence(self):
        values = self.values()
        with patch.dict(routing.os.environ, values, clear=True), \
                patch.object(routing.subprocess, "check_output", return_value=""), \
                patch.object(routing, "write_secret") as write:
            routing.ensure_webhook_secret()
        obj = write.call_args.args[0]
        self.assertTrue(write.call_args.kwargs["create"])
        self.assertEqual(obj["metadata"]["labels"]["run_token"], routing.RUN_TOKEN)
        self.assertEqual(base64.b64decode(obj["data"]["url"]).decode(), values["DEVIN_ALERT_WEBHOOK_URL"])
        obj["metadata"].update({"resourceVersion": "42", "labels": {"other": "keep"}})
        with patch.dict(routing.os.environ, values, clear=True), \
                patch.object(routing.subprocess, "check_output", return_value=json.dumps(obj)), \
                patch.object(routing, "write_secret") as write:
            routing.ensure_webhook_secret()
        current = write.call_args.args[0]
        self.assertEqual(current["metadata"]["resourceVersion"], "42")
        self.assertEqual(current["metadata"]["labels"]["other"], "keep")
        for env in ({}, values):
            with patch.dict(routing.os.environ, env, clear=True), \
                    patch.object(routing.subprocess, "check_output", return_value=json.dumps(current)), \
                    patch.object(routing, "write_secret") as write:
                routing.ensure_webhook_secret()
                write.assert_not_called()
        with patch.dict(routing.os.environ, {**values, "DEVIN_ALERT_WEBHOOK_SECRET": "rotated-fixture"}, clear=True), \
                patch.object(routing.subprocess, "check_output", return_value=json.dumps(current)), \
                patch.object(routing, "write_secret") as write:
            routing.ensure_webhook_secret()
        self.assertEqual(base64.b64decode(write.call_args.args[0]["data"]["secret"]).decode(), "rotated-fixture")
        self.assertEqual(write.call_args.args[0]["metadata"], current["metadata"])

    def test_missing_partial_and_invalid_inputs(self):
        for values in ({}, {"DEVIN_ALERT_WEBHOOK_URL": "https://example.invalid"},
                       {**self.values(), "DEVIN_ALERT_WEBHOOK_URL": "http://example.invalid"},
                       {**self.values(), "DEVIN_ALERT_WEBHOOK_SECRET": "bad\nheader"},
                       {**self.values(), "DEVIN_ALERT_WEBHOOK_URL": "https://[invalid"}):
            with self.subTest(keys=list(values)), patch.dict(routing.os.environ, values, clear=True), \
                    patch.object(routing.subprocess, "check_output", return_value=""), \
                    patch.object(routing, "write_secret") as write, self.assertRaises(ValueError):
                routing.ensure_webhook_secret()
            write.assert_not_called()

    def test_secret_write_failure_does_not_expose_payload(self):
        with patch.object(routing.subprocess, "run", return_value=subprocess.CompletedProcess(
                [], 1, stdout="sensitive fixture", stderr="sensitive fixture")), \
                self.assertRaisesRegex(RuntimeError, "output withheld") as error:
            routing.write_secret({"metadata": {"name": "fixture"}, "data": {"url": "sensitive fixture"}})
        self.assertNotIn("sensitive fixture", str(error.exception))

    def test_invalid_existing_data_and_explicit_empty_credentials(self):
        for data in (None, {}, {"url": "invalid base64"}, {"url": "/w==", "secret": "eA=="}):
            with self.subTest(data=data), patch.dict(routing.os.environ, {}, clear=True), \
                    patch.object(routing.subprocess, "check_output", return_value=json.dumps({"data": data})), \
                    patch.object(routing, "write_secret") as write, self.assertRaises(ValueError):
                routing.ensure_webhook_secret()
            write.assert_not_called()
        with patch.dict(routing.os.environ, {"DEVIN_ALERT_WEBHOOK_URL": "", "DEVIN_ALERT_WEBHOOK_SECRET": ""}, clear=True), \
                patch.object(routing, "write_secret") as write, self.assertRaises(ValueError):
            routing.ensure_webhook_secret()
        write.assert_not_called()

    def test_secret_updates_use_merge_patch_without_command_line_values(self):
        obj = {"metadata": {"name": "fixture"}, "data": {"url": "fixture-value"}}
        with patch.object(routing.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
            routing.write_secret(obj)
        self.assertEqual(run.call_args.args[0], ["kubectl", "-n", "monitoring", "patch", "secret", "fixture",
                                                "--type=merge", "--patch-file=/dev/stdin"])
        self.assertEqual(json.loads(run.call_args.kwargs["input"]), obj)
        self.assertTrue(run.call_args.kwargs["capture_output"])


if __name__ == "__main__":
    unittest.main()
