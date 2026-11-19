import importlib.util
import os
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "jobs/py"))


def legacy(tag):
    return re.sub(r"\s+", "-", (tag or "").strip().lower())


@unittest.skipUnless(importlib.util.find_spec("pyspark"), "pyspark is not installed")
class DocsTagNormalizeTest(unittest.TestCase):
    def test_matches_legacy_udf(self):
        from pyspark.sql import SparkSession
        from pyspark.sql.functions import col

        spec = importlib.util.spec_from_file_location("docs_tag_normalize", ROOT / "jobs/py/docs_tag_normalize.py")
        job = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(job)
        whitespace = [chr(code) for code in range(0x110000) if chr(code).isspace()]
        tags = [None, "", "Finance", "  Annual Review ", "Customer\t\nContract", "OPS", "a\u200bb", "x\u00a0y",
                "\u3000Mixed\u2003Case\u205f", "ÄÖÜ Straße", "\x1ctag\x1f", "--a  b--", "Ꮳ ΣΑΣ"]
        tags += [f"{space}a{space}{space}b{space}" for space in whitespace]
        os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")
        spark = (SparkSession.builder.master("local[1]").config("spark.ui.enabled", "false")
                 .config("spark.eventLog.enabled", "false").getOrCreate())
        try:
            frame = spark.createDataFrame([(index, tag) for index, tag in enumerate(tags)], "ID INT, TAG STRING")
            rows = frame.select("ID", job.normalized(col("TAG")).alias("N")).orderBy("ID").collect()
        finally:
            spark.stop()
        self.assertEqual([row.N for row in rows], [legacy(tag) for tag in tags])


if __name__ == "__main__":
    unittest.main()
