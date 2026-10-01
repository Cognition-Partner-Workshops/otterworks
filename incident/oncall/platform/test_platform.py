import copy
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

HERE = Path(__file__).parent


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


merger = load_module("merger", "merge-alertmanager-routes.py")
otel = load_module("otel", "patch-otel-tempo.py")
FAKE_URL = "https://example.invalid/FAKE_NEW_URL_SECRET"
FAKE_SECRET = "FAKE_NEW_HEADER_SECRET"


class PlatformTests(unittest.TestCase):
    def setUp(self):
        self.config = yaml.safe_load((HERE / "fixtures/alertmanager.yaml").read_text())

    def test_merge_preserves_existing_routes_receivers_and_inhibitions(self):
        original = copy.deepcopy(self.config)
        merged = merger.merge_config(self.config, FAKE_URL, FAKE_SECRET)
        self.assertEqual(self.config, original)
        routes = merged["route"]["routes"]
        self.assertEqual([r["receiver"] for r in routes[:2]], ["oncall-devin", "oncall-channel"])
        self.assertEqual(routes[2:], original["route"]["routes"])
        self.assertEqual(routes[0]["group_by"], ["namespace", "oncall_group"])
        self.assertEqual(routes[0]["group_wait"], "3m")
        self.assertEqual(routes[0]["group_interval"], "6h")
        self.assertTrue(all(r["continue"] for r in routes[:2]))
        self.assertEqual(merged["inhibit_rules"], original["inhibit_rules"])
        self.assertEqual(merged["receivers"][:2], original["receivers"])
        webhook = merged["receivers"][2]["webhook_configs"][0]
        self.assertFalse(webhook["send_resolved"])
        self.assertEqual(webhook["max_alerts"], 0)
        self.assertEqual(
            webhook["http_config"]["http_headers"]["X-Webhook-Secret"]["values"], [FAKE_SECRET]
        )

    def test_merge_is_idempotent_and_replaces_oncall_receivers(self):
        first = merger.merge_config(self.config, FAKE_URL, FAKE_SECRET)
        self.assertEqual(merger.merge_config(first, FAKE_URL, FAKE_SECRET), first)
        channel_only = merger.merge_config(first, "", "")
        self.assertNotIn("oncall-devin", [r["name"] for r in channel_only["receivers"]])
        self.assertEqual(channel_only["route"]["routes"][0]["receiver"], "oncall-channel")
        self.assertEqual(channel_only["route"]["routes"][1:], self.config["route"]["routes"])

    def test_partial_webhook_configuration_is_rejected(self):
        for url, secret in [(FAKE_URL, ""), ("", FAKE_SECRET)]:
            with self.assertRaises(ValueError):
                merger.merge_config(self.config, url, secret)

    def test_offline_cli_validates_sample_with_amtool_and_never_prints_secrets(self):
        env = {
            **os.environ,
            "ONCALL_DEVIN_WEBHOOK_URL": FAKE_URL,
            "ONCALL_DEVIN_WEBHOOK_SECRET": FAKE_SECRET,
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "sample.yaml"
            result = subprocess.run(
                [
                    "python3",
                    str(HERE / "merge-alertmanager-routes.py"),
                    "--config",
                    str(HERE / "fixtures/alertmanager.yaml"),
                    "--output",
                    str(output),
                ],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0)
            for secret in [
                FAKE_URL,
                FAKE_SECRET,
                "FAKE_OLD_DEFAULT_SECRET",
                "FAKE_OLD_DEVIN_SECRET",
                "FAKE_EXISTING_HEADER_SECRET",
            ]:
                self.assertNotIn(secret, result.stdout + result.stderr)
            self.assertIn("oncall-devin", result.stdout)
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            merged = yaml.safe_load(output.read_text())
            self.assertEqual(merged, merger.merge_config(self.config, FAKE_URL, FAKE_SECRET))

    def test_private_command_failure_suppresses_captured_output(self):
        failure = subprocess.CompletedProcess([], 1, FAKE_SECRET, FAKE_URL)
        with (
            patch.object(merger.subprocess, "run", return_value=failure),
            self.assertRaises(RuntimeError) as error,
        ):
            merger.run_private(["kubectl"])
        self.assertNotIn(FAKE_SECRET, str(error.exception))
        self.assertNotIn(FAKE_URL, str(error.exception))

    def test_live_patch_uses_resource_version_and_stdin(self):
        live = {
            "metadata": {"resourceVersion": "123"},
            "data": {
                "alertmanager.yaml": merger.base64.b64encode(
                    yaml.safe_dump(self.config).encode()
                ).decode(),
            },
        }
        env = {"ONCALL_DEVIN_WEBHOOK_URL": FAKE_URL, "ONCALL_DEVIN_WEBHOOK_SECRET": FAKE_SECRET}
        with (
            patch.dict(os.environ, env),
            patch.object(merger.sys, "argv", ["merge", "--apply"]),
            patch.object(merger, "validate_config"),
            patch.object(merger, "run_private", side_effect=[json.dumps(live), ""]) as run,
            patch("builtins.print"),
        ):
            merger.main()
        command, payload = run.call_args.args
        self.assertIn("--patch-file=/dev/stdin", command)
        self.assertNotIn(FAKE_SECRET, " ".join(command))
        patch_payload = json.loads(payload)
        self.assertEqual(
            patch_payload[0],
            {
                "op": "test",
                "path": "/metadata/resourceVersion",
                "value": "123",
            },
        )

    def test_tempo_export_preserves_jaeger_and_other_pipelines(self):
        config = {
            "exporters": {"otlp_grpc/jaeger": {"endpoint": "jaeger:4317"}},
            "service": {
                "pipelines": {
                    "traces": {"exporters": ["otlp_grpc/jaeger"]},
                    "metrics": {"exporters": ["debug"]},
                }
            },
        }
        original = copy.deepcopy(config)
        updated = otel.add_tempo(config)
        self.assertEqual(
            updated["service"]["pipelines"]["traces"]["exporters"],
            ["otlp_grpc/jaeger", "otlp_grpc/tempo"],
        )
        self.assertEqual(
            updated["exporters"]["otlp_grpc/jaeger"], original["exporters"]["otlp_grpc/jaeger"]
        )
        self.assertEqual(
            updated["service"]["pipelines"]["metrics"], original["service"]["pipelines"]["metrics"]
        )
        self.assertEqual(otel.add_tempo(updated), updated)


if __name__ == "__main__":
    unittest.main()
