import importlib.util
import os
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "jobs/py"))


def legacy_browser(agent):
    match = re.search(r"(Chrome|Firefox|Safari)/(\S+)", agent or "")
    return match.group(1) + "/" + match.group(2) if match else "Other"


@unittest.skipUnless(importlib.util.find_spec("pyspark"), "pyspark is not installed")
class UsersLoginUseragentParseTest(unittest.TestCase):
    def test_matches_legacy_python_parser(self):
        from pyspark.sql import SparkSession
        from pyspark.sql.functions import col

        spec = importlib.util.spec_from_file_location("useragent_job", ROOT / "jobs/py/users_login_useragent_parse.py")
        job = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(job)
        spaces = [chr(c) for c in range(sys.maxunicode + 1) if chr(c).isspace()]
        agents = [None, "", "curl/8.0", "Mozilla/5.0 Chrome/120.0.1 Safari/537.36", "Firefox/", "Safari/17.1",
                  "Opera Firefox/115.0esr extra", "ChromeOS Chrome/1", "Edge/1 Firefox/2 Chrome/3",
                  "Chrome/é1.0", "Chrome/1🚀2 x", "chrome/1", "XFirefox/9.9;rv"]
        agents += [f"Chrome/1{space}2" for space in spaces] + [f"Safari/{space}9" for space in spaces]
        agents += ["Chrome/1\u200b2", "Chrome/1\x1b2"]
        environment = {"SPARK_LOCAL_IP": "127.0.0.1", "PYSPARK_PYTHON": sys.executable,
                       "PYSPARK_DRIVER_PYTHON": sys.executable,
                       "PYSPARK_SUBMIT_ARGS": "--master local[1] --conf spark.ui.enabled=false pyspark-shell"}
        with patch.dict(os.environ, environment):
            spark = SparkSession.builder.appName("useragent-parity").getOrCreate()
            try:
                frame = spark.createDataFrame([(index, agent) for index, agent in enumerate(agents)],
                                              "ID int, USER_AGENT string")
                rows = frame.select("ID", job.browser(col("USER_AGENT")).alias("BROWSER")).collect()
            finally:
                spark.stop()
        self.assertEqual({row.ID: row.BROWSER for row in rows},
                         {index: legacy_browser(agent) for index, agent in enumerate(agents)})
