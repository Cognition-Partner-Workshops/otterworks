# run_token=dbx-d1111 expires=2026-11-24
# Local check: python logic vs the original Scala job output (LAKE_DIR) on the same landing files (LANDING_DIR).
import os
import unittest

from pyspark.sql import SparkSession

from team_graph_components import components


class TeamGraphComponentsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spark = SparkSession.builder.master("local[2]").config("spark.eventLog.enabled", "false").getOrCreate()

    def test_matches_original_output(self):
        landing, lake = os.environ["LANDING_DIR"], os.environ["LAKE_DIR"]
        members = (self.spark.read.option("header", "true").option("sep", "|").option("escape", '"')
                   .option("inferSchema", "true").csv(f"{landing}/users/TEAM_MEMBER/*.psv"))
        expected = self.spark.read.parquet(f"{lake}/users/team_graph_components")
        actual = components(members)
        self.assertEqual(sorted(expected.collect()), sorted(actual.collect()))

    def test_bounded_iterations(self):
        # Path 1-2-...-9 via two-member teams: after 6 rounds node 9 has only reached label 3.
        rows = [(t, u) for t in range(1, 9) for u in (t, t + 1)]
        members = self.spark.createDataFrame(rows, "TEAM_ID int, USER_ID int")
        labels = dict(components(members).collect())
        self.assertEqual(labels[9], 3)
        self.assertEqual(labels[7], 1)


if __name__ == "__main__":
    unittest.main()
