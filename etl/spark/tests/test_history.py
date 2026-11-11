import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "history"))
import compute_baseline as baseline
from eventlog import compress, decompress, read_events, write_events
from shift_eventlog import shift_log, shift_value


START = 1794339000000
APP_ID = "app-20261110193000-0000"


def application():
    return [
        {"Event": "SparkListenerApplicationStart", "Timestamp": START,
         "App Name": "monthly_summary", "App ID": APP_ID},
        {"Event": "SparkListenerExecutorAdded", "Timestamp": START + 1000,
         "Executor ID": "0", "Executor Info": {"Total Cores": 2}},
        {"Event": "SparkListenerExecutorAdded", "Timestamp": START + 2000,
         "Executor ID": "1", "Executor Info": {"Total Cores": 3}},
        {"Event": "SparkListenerExecutorRemoved", "Timestamp": START + 4000, "Executor ID": "0"},
        {"Event": "SparkListenerTaskEnd", "Task End Reason": {"Reason": "ExceptionFailure"},
         "Task Info": {"Failed": True}, "Task Metrics": {"Memory Bytes Spilled": 20, "Disk Bytes Spilled": 10}},
        {"Event": "SparkListenerTaskEnd", "Task End Reason": {"Reason": "Success"},
         "Task Info": {"Failed": False}, "Task Metrics": {"Memory Bytes Spilled": 30, "Disk Bytes Spilled": 15}},
        {"Event": "SparkListenerStageCompleted", "Stage Info": {"Accumulables": [
            {"ID": 12, "Name": "number of written files", "Value": "4"}]}},
        {"Event": "SparkListenerStageCompleted", "Stage Info": {"Accumulables": [
            {"ID": 12, "Name": "number of written files", "Value": "10"}]}},
        {"Event": "SparkListenerApplicationEnd", "Timestamp": START + 10000},
    ]


class HistoryTest(unittest.TestCase):
    def test_zstd(self):
        for data in (b"", b"event\n" * 100000):
            self.assertEqual(decompress(compress(data)), data)
        self.assertEqual(decompress(compress(b"one") + compress(b"two")), b"onetwo")
        for data in (b"", b"invalid", compress(b"event")[:-1]):
            with self.assertRaises(ValueError):
                decompress(data)

    def test_event_log_roundtrip_and_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.zstd"
            write_events(path, application())
            self.assertEqual(list(read_events(path)), application())
            write_events(path, [])
            self.assertEqual(list(read_events(path)), [])
            path.write_bytes(compress(b"{invalid}\n"))
            with self.assertRaisesRegex(ValueError, ":1:"):
                list(read_events(path))

    def test_metrics(self):
        name, result = baseline.summarize(application())
        self.assertEqual(name, "monthly_summary")
        self.assertEqual(result["runtime_seconds"], 10)
        self.assertEqual(result["executor_count"], 2)
        self.assertEqual(result["executor_hours"], round(11000 / 3600000, 9))
        self.assertEqual(result["core_hours"], round(30000 / 3600000, 9))
        self.assertEqual(result["failed_tasks"], 1)
        self.assertEqual(result["memory_bytes_spilled"], 50)
        self.assertEqual(result["disk_bytes_spilled"], 25)
        self.assertEqual(result["output_files_written"], 10)

    def test_empty_and_incomplete_application(self):
        for events in ([], application()[:-1]):
            with self.assertRaises(ValueError):
                baseline.summarize(events)
        events = [application()[0], application()[-1]]
        _, result = baseline.summarize(events)
        self.assertEqual(result["executor_count"], 0)
        self.assertEqual(result["executor_hours"], 0)
        self.assertIsNone(result["output_files_written"])

    def test_inventory_and_check(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            logs = root / "eventlogs"
            logs.mkdir()
            path = logs / (APP_ID + ".zstd")
            write_events(path, application())
            with self.assertRaisesRegex(ValueError, "inventory differs"):
                baseline.compute(logs, [])
            result = baseline.compute(logs, ["monthly_summary"])
            self.assertEqual(result["totals"]["applications"], 1)
            (root / "jobs.txt").write_text("monthly_summary\n")
            history = root / "history"
            history.mkdir()
            output = root / "baseline.json"
            arguments = ["compute_baseline.py", "--log-dir", str(logs), "--output", str(output), "--check"]
            with patch.object(baseline, "ROOT", history), patch.object(sys, "argv", arguments):
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(baseline.main(), 1)
                output.write_text(json.dumps(result))
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(baseline.main(), 0)
                result["totals"]["applications"] = 2
                output.write_text(json.dumps(result))
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(baseline.main(), 1)
            duplicate = logs / "duplicate.zstd"
            write_events(duplicate, application())
            with self.assertRaises(ValueError):
                baseline.compute(logs, ["monthly_summary"])

    def test_timestamp_shift_and_idempotence(self):
        offset = -118 * 86400000
        event = {
            "Stage Info": {"Submission Time": START, "Completion Time": START + 1000},
            "Task Info": {"Launch Time": START, "Getting Result Time": 0, "Finish Time": START + 1000},
            "time": START, "Timestamp": START, "Executor Run Time": 1000,
            "spark.app.startTime": str(START), "spark.app.id": APP_ID,
            "Executor Info": {"Registration Time": START, "Request Time": START - 1000},
        }
        shifted = shift_value(event, offset, APP_ID, "new-id")
        self.assertEqual(shifted["Task Info"]["Getting Result Time"], 0)
        self.assertEqual(shifted["Executor Run Time"], 1000)
        self.assertEqual(shifted["time"], START + offset)
        self.assertEqual(shifted["Stage Info"]["Submission Time"], START + offset)
        self.assertEqual(shifted["Task Info"]["Finish Time"], START + 1000 + offset)
        self.assertEqual(shifted["spark.app.startTime"], str(START + offset))
        self.assertEqual(shifted["spark.app.id"], "new-id")
        self.assertEqual(shifted["Executor Info"]["Registration Time"], START + offset)
        self.assertEqual(shifted["Executor Info"]["Request Time"], START - 1000 + offset)
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / (APP_ID + ".zstd")
            write_events(original, application())
            shifted_path = shift_log(original, START, 118)
            self.assertFalse(original.exists())
            events = list(read_events(shifted_path))
            self.assertEqual(events[0]["Timestamp"], START + offset)
            self.assertEqual(events[-1]["Timestamp"], START + 10000 + offset)
            self.assertEqual(events[1]["Timestamp"], START + 1000 + offset)
            self.assertEqual(shifted_path.stem, events[0]["App ID"])
            before = shifted_path.read_bytes()
            self.assertEqual(shift_log(shifted_path, START, 118), shifted_path)
            self.assertEqual(shifted_path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
