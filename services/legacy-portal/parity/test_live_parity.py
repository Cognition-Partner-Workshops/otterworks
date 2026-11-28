import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import live_parity


class LiveParityTest(unittest.TestCase):
    def test_state_only_normalizes_timestamp_columns(self):
        first = "2026-01-02T03:04:05.123"
        second = "2026-01-02T03:04:06"

        def snapshot(timestamp, title):
            return live_parity.normalized_state(json.dumps({
                "announcements.announcement": [{"created_at": timestamp, "title": title}],
            }))

        self.assertEqual(snapshot(first, first), snapshot(second, first))
        self.assertNotEqual(snapshot(first, first), snapshot(second, second))

    def test_late_snapshot_error_retains_responses(self):
        args = SimpleNamespace(reset_cmd="", state_cmd="", java_base="java", lambda_base="lambda",
                               timeout=1, strict_media_type=False, stage="full")
        cases = [{"id": n, "method": method, "path": "/"} for n, method in
                 (("initial", "GET"), ("write", "POST"), ("later", "GET"))]
        response = {"status": 200, "body": "{}", "mediaType": "application/json",
                    "sentUtc": "", "elapsedMs": 0, "identity": {}}
        reference = {case["id"]: response for case in cases}
        with patch.object(live_parity, "run_cmd"), patch.object(live_parity, "send", return_value=response), \
                patch.object(live_parity, "snapshots", side_effect=[{"java": {}, "lambda": {}},
                                                                  RuntimeError("snapshot failed")]):
            result = live_parity.run_context("common", cases, reference, args)
        initial, write = result["cases"]
        self.assertTrue(initial["passed"])
        self.assertEqual(write["lambda"]["status"], 200)
        self.assertFalse(write["passed"])
        self.assertIsNone(write["state"])
        self.assertEqual(result["error"], "write: snapshot failed")
