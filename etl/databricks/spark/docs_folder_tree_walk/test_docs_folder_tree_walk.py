# run_token=dbx-d1111 expires=2026-11-24
# Local check: python logic vs the original job output on the generated fixture and on edge cases.
import os
import unittest

from pyspark.sql import SparkSession

from docs_folder_tree_walk import walk


def original(sc, pairs):
    parents = sc.parallelize(pairs)
    lookup = dict(parents.collect())
    paths = parents.map(lambda r: (r[0], r[0], 0))
    for _ in range(20):
        paths = paths.map(lambda r: (r[0], lookup.get(r[1]) or r[1], r[2] + int(lookup.get(r[1]) is not None)))
    return sorted(paths.collect())


class DocsFolderTreeWalkTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spark = SparkSession.builder.master("local[2]").config("spark.eventLog.enabled", "false").getOrCreate()

    def test_matches_original_output(self):
        lake = os.environ["LAKE_DIR"]
        folders = (self.spark.read.option("header", "true").option("sep", "|")
                   .schema("FOLDER_ID long, OWNER_USER_ID long, PARENT_FOLDER_ID long, FOLDER_NAME string")
                   .csv(f"{os.environ['LANDING_DIR']}/documents/FOLDER/*.psv"))
        expected = self.spark.read.parquet(f"{lake}/documents/docs_folder_tree_walk")
        self.assertEqual(sorted(expected.collect()), sorted(walk(folders).collect()))

    def test_edge_cases(self):
        pairs = [(1, None), (2, 1), (3, 2), (4, 0), (5, 99), (6, 7), (7, 6)]
        frame = self.spark.createDataFrame(pairs, "FOLDER_ID long, PARENT_FOLDER_ID long")
        actual = sorted(tuple(r) for r in walk(frame).collect())
        self.assertEqual(original(self.spark.sparkContext, pairs), actual)


if __name__ == "__main__":
    unittest.main()
