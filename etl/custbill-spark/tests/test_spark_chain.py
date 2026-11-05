"""End-to-end behaviour of the Spark chain that the legacy scripts never had."""

import fcntl
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from custbill_spark import __main__ as cli
from custbill_spark import ingest, parse, report, support
from custbill_spark.config import Settings
from custbill_spark.support import LockBusy, build_session

FIXTURES = Path(__file__).resolve().parents[2] / "legacy-extra/parity/fixtures"

try:
    import pyspark  # noqa: F401
    HAVE_SPARK = True
except ImportError:
    HAVE_SPARK = False


def tree_digest(root):
    digest = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and "control" not in path.relative_to(root).parts:
            digest[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest


@unittest.skipUnless(HAVE_SPARK, "pyspark not installed (make -C etl/legacy-extra spark-venv)")
class SparkChain(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="custbill-spark-test-")
        cls.spark = build_session(Settings(root=Path(cls.tmp), spark_master="local[2]"), "custbill-tests")

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def estate(self, name, *fixtures, **overrides):
        root = Path(self.tmp) / name
        (root / "sftp-drop/upload").mkdir(parents=True)
        for fixture in fixtures:
            shutil.copy(FIXTURES / fixture, root / "sftp-drop/upload" / fixture)
        return Settings(root=root, spark_master="local[2]", **overrides)

    def test_chain_is_idempotent_and_surfaces_quality(self):
        settings = self.estate("edges", "CUSTBILL_EDGES.dat", "CUSTBILL_HEADER_ONLY.dat")
        cli.run_chain(settings, self.spark)
        first = tree_digest(settings.root)
        self.assertIn("parsed/CUSTBILL_EDGES.psv", first)
        self.assertIn("incoming/CUSTBILL_EDGES.dat.done", first)
        self.assertEqual(len([k for k in first if k.startswith("reports/")]), 2)
        ledger = json.loads((settings.control / "parse/latest.json").read_text())
        edges = ledger["files"]["CUSTBILL_EDGES.dat"]
        self.assertFalse(edges["trailer_reconciled"])
        self.assertEqual((edges["trailer_count"], edges["records"]), (99, 4))
        self.assertTrue(any("bad-record-type" in s["reasons"] for s in edges["invalid_sample"]))
        self.assertTrue(ledger["files"]["CUSTBILL_HEADER_ONLY.dat"]["trailer_reconciled"])
        cli.run_chain(settings, self.spark)
        self.assertEqual(tree_digest(settings.root), first)

    def test_strict_mode_quarantines_instead_of_reporting(self):
        settings = self.estate("strict", "CUSTBILL_EDGES.dat", strict=True)
        with self.assertRaises(RuntimeError):
            cli.run_chain(settings, self.spark)
        self.assertFalse((settings.parsed / "CUSTBILL_EDGES.psv").exists())
        self.assertTrue((settings.incoming / "CUSTBILL_EDGES.dat").exists())
        self.assertEqual(json.loads((settings.control / "parse/latest.json").read_text())["quarantined"],
                         ["CUSTBILL_EDGES.dat"])

    def test_ingest_defers_incomplete_uploads(self):
        settings = self.estate("partial", "CUSTBILL_EDGES.dat")
        data = (FIXTURES / "CUSTBILL_EDGES.dat").read_bytes()
        (settings.drop / "CUSTBILL_TRUNC.dat").write_bytes(data[:-20])
        (settings.drop / "CUSTBILL_MANIFEST.dat").write_bytes(data)
        (settings.drop / "CUSTBILL_MANIFEST.dat.sha256").write_text("0" * 64 + "\n")
        ledger = ingest.run(settings, self.spark)
        self.assertEqual([s["file"] for s in ledger["staged"]], ["CUSTBILL_EDGES.dat"])
        self.assertEqual(sorted(d["file"] for d in ledger["deferred"]),
                         ["CUSTBILL_MANIFEST.dat", "CUSTBILL_TRUNC.dat"])
        self.assertTrue((settings.drop / "CUSTBILL_TRUNC.dat").exists())
        (settings.drop / "CUSTBILL_MANIFEST.dat.sha256").write_text(hashlib.sha256(data).hexdigest() + "\n")
        ledger = ingest.run(settings, self.spark)
        self.assertEqual([s["file"] for s in ledger["staged"]], ["CUSTBILL_MANIFEST.dat"])
        self.assertFalse((settings.drop / "CUSTBILL_MANIFEST.dat.sha256").exists())

    def test_lock_prevents_overlapping_runs(self):
        settings = self.estate("locked")
        lock = settings.control / "locks/chain.lock"
        lock.parent.mkdir(parents=True)
        with lock.open("w") as holder:
            fcntl.flock(holder, fcntl.LOCK_EX)
            with self.assertRaises(LockBusy):
                cli.run_chain(settings, self.spark)

    def test_report_delivery_is_verified(self):
        settings = self.estate("deliver", delivery_dir=Path(self.tmp) / "deliver/outbox",
                               distribution=("finance-billing@example.invalid",))
        ledger = report.run(settings, self.spark)
        delivered = Path(ledger["delivered_to"])
        self.assertEqual(delivered.read_bytes(), b"Currency,RecordType,RecordCount,TotalAmount\n")
        self.assertEqual(ledger["distribution"], ["finance-billing@example.invalid"])

    def test_empty_estate_parses_nothing(self):
        settings = self.estate("empty")
        settings.incoming.mkdir()
        self.assertEqual(parse.run(settings, self.spark), {"files": {}})

    def test_delivery_to_report_directory(self):
        settings = self.estate("deliver-self")
        settings.delivery_dir = settings.reports
        ledger = report.run(settings, self.spark)
        self.assertEqual(Path(ledger["delivered_to"]).read_bytes(),
                         b"Currency,RecordType,RecordCount,TotalAmount\n")

    def test_failed_delivery_preserves_previous_copy(self):
        settings = self.estate("deliver-fail", delivery_dir=Path(self.tmp) / "outbox-fail")
        ledger = report.run(settings, self.spark)
        target = Path(ledger["delivered_to"])
        target.write_bytes(b"previous delivery")
        original = support.os.replace

        def fail_delivery(source, dest):
            if dest == target:
                raise OSError("delivery unavailable")
            return original(source, dest)

        with patch.object(support.os, "replace", side_effect=fail_delivery):
            with self.assertRaisesRegex(OSError, "delivery unavailable"):
                report.run(settings, self.spark)
        self.assertEqual(target.read_bytes(), b"previous delivery")
        self.assertEqual(list(target.parent.glob(".*.tmp-*")), [])


if __name__ == "__main__":
    unittest.main()
