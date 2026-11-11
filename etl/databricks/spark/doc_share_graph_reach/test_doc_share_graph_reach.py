# run_token=dbx-d1111 expires=2026-11-24
# Local check: python logic vs the original job output and vs the original RDD algorithm on a synthetic graph.
import os
import unittest

from pyspark.sql import SparkSession

from doc_share_graph_reach import reach


def original(sc, pairs):
    edges = sc.parallelize(pairs).cache()
    frontier = sc.parallelize([(1, 0)], 2)
    visited = frontier
    for depth in range(1, 5):
        frontier = frontier.join(edges).map(lambda r: (r[1][1], depth)).subtractByKey(visited).cache()
        visited = visited.union(frontier).reduceByKey(min)
    return sorted(visited.collect())


class DocShareGraphReachTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spark = SparkSession.builder.master("local[2]").config("spark.eventLog.enabled", "false").getOrCreate()

    def frame(self, pairs):
        return self.spark.createDataFrame(pairs, "OWNER_USER_ID long, SHARED_WITH_USER_ID long")

    def test_matches_original_output(self):
        lake = os.environ["LAKE_DIR"]
        expected = self.spark.read.parquet(f"{lake}/documents/doc_share_graph_reach")
        shares = (self.spark.read.option("header", "true").option("sep", "|")
                  .schema("DOC_SHARE_ID long, DOCUMENT_ID long, OWNER_USER_ID long, SHARED_WITH_USER_ID long, PERMISSION string")
                  .csv(f"{os.environ['LANDING_DIR']}/documents/DOC_SHARE/*.psv"))
        self.assertEqual(sorted(expected.collect()), sorted(reach(self.spark, shares).collect()))

    def test_synthetic_graph(self):
        pairs = [(1, 2), (1, 3), (2, 4), (3, 4), (4, 5), (5, 6), (6, 7), (2, 1), (5, 5), (8, 9), (1, 2)]
        actual = sorted(tuple(r) for r in reach(self.spark, self.frame(pairs)).collect())
        self.assertEqual(original(self.spark.sparkContext, pairs), actual)


if __name__ == "__main__":
    unittest.main()
