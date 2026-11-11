import contextlib
import csv
from decimal import Decimal
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

try:
    from pyspark.sql import SparkSession
    from pyspark.sql.functions import col, sum as total
except ImportError:
    SparkSession = None

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "fixture"))
from generate_fixture import generate


@unittest.skipUnless(importlib.util.find_spec("pyspark"), "pyspark is not installed")
class LocalTest(unittest.TestCase):
    def test_python_jobs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            landing = root / "landing"
            lake = root / "lake"
            with contextlib.redirect_stdout(io.StringIO()):
                generate(landing, 2000, 1110)
            environment = {
                **os.environ,
                "LANDING_DIR": str(landing), "LAKE_DIR": str(lake),
                "SPARK_LOCAL_IP": "127.0.0.1",
                "PYSPARK_PYTHON": sys.executable,
                "PYSPARK_DRIVER_PYTHON": sys.executable,
                "PYTHONPATH": str(ROOT / "jobs/py"),
                "PYSPARK_SUBMIT_ARGS": "--master local[2] --conf spark.ui.enabled=false --conf spark.sql.shuffle.partitions=2 --conf spark.default.parallelism=2 --conf spark.eventLog.enabled=false pyspark-shell",
            }
            for job in ("billing_revenue_by_plan", "docs_tag_normalize", "user_pref_json_flatten"):
                completed = subprocess.run(
                    [sys.executable, str(ROOT / "jobs/py" / f"{job}.py")],
                    env=environment, cwd=root, capture_output=True, text=True, timeout=120,
                )
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            with patch.dict(os.environ, environment):
                spark = SparkSession.builder.appName("local-verification").getOrCreate()
                try:
                    self.assertEqual(spark.sparkContext._jvm.java.lang.System.getProperty("java.specification.version"), "17")
                    tags = spark.read.parquet(str(lake / "documents/docs_tag_normalize"))
                    self.assertEqual(tags.count(), 2000)
                    self.assertEqual(tags.filter(col("NORMALIZED_TAG").isin("finance", "report", "annual-review", "ops", "customer-contract")).count(), 2000)
                    preferences = spark.read.parquet(str(lake / "users/user_pref_json_flatten"))
                    self.assertEqual(preferences.count(), 2000)
                    self.assertEqual(preferences.filter(col("THEME").isin("dark", "light")).count(), 2000)
                    revenue = spark.read.parquet(str(lake / "billing/billing_revenue_by_plan"))
                    self.assertEqual(revenue.count(), 12)
                    with (landing / "billing/INVOICE_LINE/20261109.psv").open() as stream:
                        expected = sum(Decimal(row["AMOUNT"]) for row in csv.DictReader(stream, delimiter="|"))
                    self.assertEqual(revenue.agg(total("REVENUE")).first()[0], expected)
                finally:
                    spark.stop()
            print("LOCAL_JOBS billing_revenue_by_plan docs_tag_normalize user_pref_json_flatten: OK (2000 rows)")


if __name__ == "__main__":
    unittest.main()
