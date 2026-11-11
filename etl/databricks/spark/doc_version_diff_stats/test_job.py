# run_token=dbx-d1111 expires=2026-11-24
import difflib
import unittest
from pathlib import Path

from job import similarity, transform
from pyspark.sql import SparkSession


class SimilarityTests(unittest.TestCase):
    def test_null_empty_and_sequence_matcher_semantics(self):
        for before, after in ((None, None), (None, "abc"), ("abc", "abc"), ("abc", "ab"), ("x" * 400, "x" * 399)):
            self.assertEqual(similarity(before, after), difflib.SequenceMatcher(None, before or "", after or "").ratio())

    def test_window_orders_within_document_and_preserves_nulls(self):
        spark = SparkSession.builder.master("local[2]").appName("diff_unit_tests").getOrCreate()
        try:
            spark.sparkContext.addPyFile(str(Path(__file__).with_name("job.py")))
            frame = spark.createDataFrame([(1, 2, "ab"), (1, 1, "abc"), (2, 1, None)], "DOCUMENT_ID LONG, VERSION_NUMBER LONG, BODY STRING")
            rows = transform(frame).orderBy("DOCUMENT_ID", "VERSION_NUMBER").collect()
            self.assertEqual([r.PREVIOUS_BODY for r in rows], [None, "abc", None])
            self.assertEqual([r.SIMILARITY for r in rows], [0.0, 0.8, 1.0])
        finally:
            spark.stop()


if __name__ == "__main__":
    unittest.main()
