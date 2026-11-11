import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jobs/py"))

try:
    from pyspark.sql import SparkSession
except ImportError:
    SparkSession = None


@unittest.skipIf(SparkSession is None, "pyspark is not installed")
class LegacyOutputMigration(unittest.TestCase):
    def test_partitioned_run_replaces_legacy_root_files(self):
        import file_object_binary_extract as job
        from common.runtime import save_partition

        spark = SparkSession.builder.master("local[1]").config("spark.ui.enabled", "false").getOrCreate()
        with tempfile.TemporaryDirectory() as lake, patch.dict(os.environ, {"LAKE_DIR": lake}):
            path = Path(lake) / "documents/file_object_binary_extract"
            spark.createDataFrame([("legacy", 1)], ["STORAGE_KEY", "PAGE_COUNT"]).write.parquet(str(path))
            job.drop_unpartitioned(path)
            frame = spark.createDataFrame([("new", 2)], ["STORAGE_KEY", "PAGE_COUNT"])
            save_partition(frame, "documents", "file_object_binary_extract", "2026-11-10")
            self.assertEqual(sorted(p.name for p in path.iterdir() if not p.name.startswith(("_", "."))),
                             ["run_date=2026-11-10"])
            rows = spark.read.parquet(str(path)).collect()
            self.assertEqual([(r.STORAGE_KEY, str(r.run_date)) for r in rows], [("new", "2026-11-10")])


if __name__ == "__main__":
    unittest.main()
