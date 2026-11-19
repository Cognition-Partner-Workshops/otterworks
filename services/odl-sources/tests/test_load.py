import subprocess
from types import SimpleNamespace
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from odl_sources import load


class LoaderTests(unittest.TestCase):
    def test_batches(self):
        self.assertEqual(list(load.batches([], 2)), [])
        self.assertEqual(list(load.batches(range(5), 2)), [[0, 1], [2, 3], [4]])

    def test_db2_session(self):
        with patch.object(load.subprocess, "run") as run:
            load.db2_exec("db2 connect to ODL; db2 -x 'VALUES 1'")
            command = run.call_args.args[0][-1]
            self.assertIn("; status=$?;", command)
            self.assertTrue(command.endswith("exit $status"))
        with patch.object(load.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "kubectl")):
            with self.assertRaises(subprocess.CalledProcessError):
                load.db2_exec("db2 connect to ODL")

    def test_retry_and_deadline(self):
        settings = load.Settings()
        with patch.object(load, "postgres", side_effect=[ConnectionError(), None]) as source, \
             patch.object(load.time, "sleep"):
            load.load_with_retry("postgres", settings)
            self.assertEqual(source.call_count, 2)
        with patch.object(load, "postgres", side_effect=ConnectionError()), \
             patch.object(load.time, "monotonic", side_effect=[0, 1000]):
            with self.assertRaises(ConnectionError):
                load.load_with_retry("postgres", settings)

    def test_db2_load_count_session(self):
        with patch.object(load, "db2_exec", side_effect=[
            SimpleNamespace(returncode=0), SimpleNamespace(returncode=1),
            SimpleNamespace(returncode=0),
        ]) as execute, patch.object(load.subprocess, "run"):
            load.db2(load.Settings(db2_customers=2, db2_history=4))
        command = execute.call_args.args[0]
        self.assertIn("LOAD FROM /seed/history.del", command)
        self.assertIn("SELECT COUNT(*) FROM ODL.ACCTHIST' > /seed/history.count", command)
        self.assertNotIn("$(db2", command)


if __name__ == "__main__":
    unittest.main()
