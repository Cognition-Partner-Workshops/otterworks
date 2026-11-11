from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import measure
import screenshot
from eventlog import compress
from test_history import application


class MeasureTest(unittest.TestCase):
    def test_rest_event_log_metrics(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as zipped:
            zipped.writestr("app.zstd", compress(b"\n".join(json.dumps(event).encode() for event in application())))
        with patch.object(measure, "urlopen", side_effect=[io.BytesIO(b'{"attempts":[{"completed":true}]}'), io.BytesIO(archive.getvalue())]):
            result = measure.spark_measure("app")
        _, expected = measure.summarize(application())
        self.assertEqual({key: result[key] for key in expected}, expected)

    def test_spark_incomplete_or_empty(self):
        with patch.object(measure, "urlopen", return_value=io.BytesIO(b'{"attempts":[{"completed":false}]}')):
            with self.assertRaisesRegex(ValueError, "completed"):
                measure.spark_measure("app")
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w"):
            pass
        with patch.object(measure, "urlopen", side_effect=[io.BytesIO(b'{"attempts":[{"completed":true}]}'), io.BytesIO(archive.getvalue())]):
            with self.assertRaisesRegex(ValueError, "No zstd"):
                measure.spark_measure("app")

    def test_snowflake_intervals(self):
        start = datetime(2026, 11, 10, tzinfo=timezone.utc)
        rows = [{"WAREHOUSE_NAME": "SFX_D1110_TRANSFORM_WH", "WAREHOUSE_SIZE": "X-Small",
                 "START_TIME": start + timedelta(seconds=a), "END_TIME": start + timedelta(seconds=b),
                 "EXECUTION_TIME": 1000, "EXECUTION_STATUS": "SUCCESS"} for a, b in ((0, 10), (5, 15), (20, 25))]
        metrics = measure.snowflake_metrics(rows, "job")
        self.assertEqual(metrics["runtime_seconds"], 25)
        self.assertEqual(metrics["warehouse_busy_hours"], 20 / 3600)
        self.assertEqual(metrics["summed_execution_seconds"], 3)
        self.assertEqual(metrics["warehouses"][0]["sizes"], ["X-Small"])
        cached = {**rows[0], "WAREHOUSE_SIZE": None, "START_TIME": start + timedelta(seconds=30),
                  "END_TIME": start + timedelta(seconds=60)}
        self.assertEqual(measure.snowflake_metrics(rows + [cached], "job")["warehouse_busy_hours"], 20 / 3600)
        with self.assertRaises(ValueError):
            measure.snowflake_metrics([], "job")
        with self.assertRaises(ValueError):
            measure.busy_hours([(start + timedelta(seconds=1), start)])
        self.assertEqual(measure.busy_hours([]), 0)
        with self.assertRaisesRegex(ValueError, "timezone"):
            measure.snowflake_measure("job", "2026-11-10")

    def test_compare(self):
        text = measure.compare({"job": "one", "runtime_seconds": 1}, {"job": "one", "runtime_seconds": 2, "executor_hours": 0.1})
        self.assertIn("| runtime_seconds | 1 | 2 |", text)
        self.assertIn("| executor_hours | N/A | 0.1 |", text)


class ScreenshotTest(unittest.TestCase):
    def test_heaviest(self):
        self.assertEqual(screenshot.heaviest_stage([{"stageId": 1, "attemptId": 0, "executorRunTime": 10},
                                                   {"stageId": 2, "attemptId": 0, "executorRunTime": 20}])["stageId"], 2)
        with self.assertRaises(ValueError):
            screenshot.heaviest_stage([])

    def test_capture(self):
        playwright = MagicMock()
        browser = playwright.sync_playwright.return_value.__enter__.return_value.chromium.launch.return_value
        page = browser.new_page.return_value
        with tempfile.TemporaryDirectory() as directory, patch.dict(sys.modules, {"playwright.sync_api": playwright}), patch.object(
            screenshot, "urlopen", return_value=io.BytesIO(b'[{"stageId":2,"attemptId":0,"executorRunTime":20}]')
        ):
            paths = screenshot.capture("app", directory)
        self.assertEqual(len(paths), 2)
        self.assertEqual(page.screenshot.call_count, 2)
        self.assertTrue(all(call.kwargs["full_page"] for call in page.screenshot.call_args_list))
        browser.close.assert_called_once()

    def test_page_failure(self):
        playwright = MagicMock()
        browser = playwright.sync_playwright.return_value.__enter__.return_value.chromium.launch.return_value
        browser.new_page.return_value.goto.return_value.ok = False
        with tempfile.TemporaryDirectory() as directory, patch.dict(sys.modules, {"playwright.sync_api": playwright}), patch.object(
            screenshot, "urlopen", return_value=io.BytesIO(b'[{"stageId":2,"attemptId":0}]')
        ):
            with self.assertRaisesRegex(RuntimeError, "page failed"):
                screenshot.capture("app", directory)
        browser.close.assert_called_once()
