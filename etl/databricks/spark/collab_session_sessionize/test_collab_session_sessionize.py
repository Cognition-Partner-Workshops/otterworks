# run_token=dbx-d1111 expires=2026-11-24
# Local check: the SQL file (table reference swapped for a temp view) vs the original job output.
import os
import re
import unittest

from pyspark.sql import SparkSession

HERE = os.path.dirname(os.path.abspath(__file__))


def query():
    text = open(os.path.join(HERE, "collab_session_sessionize.sql")).read()
    body = text[text.index("WITH events AS"):].rstrip().rstrip(";")
    return body.replace("cpw.dbx_d1111_before.documents__collab_session", "live_collab_session")


class CollabSessionSessionizeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spark = (SparkSession.builder.master("local[2]").config("spark.eventLog.enabled", "false")
                     .config("spark.sql.session.timeZone", "UTC").getOrCreate())

    def test_matches_original_output(self):
        landing, lake = os.environ["LANDING_DIR"], os.environ["LAKE_DIR"]
        events = (self.spark.read.option("header", "true").option("sep", "|")
                  .schema("COLLAB_SESSION_ID long, DOCUMENT_ID long, USER_ID long, SESSION_ID string, EVENT_AT timestamp")
                  .csv(f"{landing}/documents/COLLAB_SESSION/*.psv"))
        events.selectExpr("COLLAB_SESSION_ID AS session_id", "DOCUMENT_ID AS document_id", "USER_ID AS user_id",
                          "EVENT_AT AS start_ts").createOrReplaceTempView("live_collab_session")
        expected = self.spark.read.parquet(f"{lake}/documents/collab_session_sessionize")
        self.assertEqual(sorted(expected.collect()), sorted(self.spark.sql(query()).collect()))

    def test_gap_boundary(self):
        self.spark.sql("""SELECT * FROM VALUES
            (1, 1, 1, TIMESTAMP'2026-01-01 00:00:00'), (2, 1, 1, TIMESTAMP'2026-01-01 00:30:00'),
            (3, 1, 1, TIMESTAMP'2026-01-01 01:00:00.000001'), (4, 1, 2, TIMESTAMP'2026-01-01 00:00:00')
            AS t(session_id, document_id, user_id, start_ts)""").createOrReplaceTempView("live_collab_session")
        rows = sorted(tuple(r) for r in self.spark.sql(query()).collect())
        self.assertEqual([(r[0], r[1], r[2]) for r in rows], [(1, 1, 1), (1, 1, 2), (2, 1, 1)])


if __name__ == "__main__":
    unittest.main()
