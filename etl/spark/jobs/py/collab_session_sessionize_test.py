from datetime import datetime, timedelta
import os
import unittest
from unittest.mock import patch

from pyspark.sql import SparkSession

from collab_session_sessionize import main, sessionize


class SessionizeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spark = SparkSession.builder.master("local[2]").appName("sessionize-test").config(
            "spark.ui.enabled", "false").config("spark.sql.shuffle.partitions", "2").getOrCreate()

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def test_boundaries(self):
        start = datetime(2026, 11, 9)
        end = start + timedelta(seconds=1800)
        next_start = end + timedelta(seconds=1800, microseconds=1)
        events = [(1, 2, next_start), (1, 2, end), (1, 2, start), (1, 2, start),
                  (2, 2, start), (1, 3, start)]
        result = sessionize(self.spark.createDataFrame(
            events, "USER_ID long, DOCUMENT_ID long, EVENT_AT timestamp")).collect()
        self.assertEqual(sorted(map(tuple, result)), [
            (1, 2, 1, start, end), (1, 2, 2, next_start, next_start),
            (1, 3, 1, start, start), (2, 2, 1, start, start),
        ])

    def test_empty(self):
        result = sessionize(self.spark.createDataFrame(
            [], "USER_ID long, DOCUMENT_ID long, EVENT_AT timestamp"))
        self.assertEqual(result.count(), 0)
        self.assertEqual(result.columns, ["USER_ID", "DOCUMENT_ID", "SESSION_NUMBER", "START_AT", "END_AT"])

    def test_invalid_date_before_spark_or_cleanup(self):
        with patch.dict(os.environ, {"SFX_RUN_DATE": "../invalid"}), patch(
                "collab_session_sessionize.session") as create:
            with self.assertRaisesRegex(ValueError, "run_date"):
                main()
            create.assert_not_called()


if __name__ == "__main__":
    unittest.main()
