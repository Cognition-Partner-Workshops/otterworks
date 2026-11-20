import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(importlib.util.find_spec("pyspark") and shutil.which("java"),
                     "PySpark and Java are required")
class AuditDailySummaryTest(unittest.TestCase):
    def test_summary(self):
        import pyspark

        spark = Path(pyspark.__file__).parent
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            classes = directory / "classes"
            classes.mkdir()
            source = ROOT / "scala/src/main/scala/sfx"
            result = subprocess.run([
                "java", "-cp", str(spark / "jars/*"), "scala.tools.nsc.Main",
                "-classpath", str(spark / "jars/*"), "-d", str(classes),
                str(source / "BatchSupport.scala"), str(source / "AuditDailySummary.scala"),
                str(ROOT / "tests/AuditDailySummaryCheck.scala"),
            ], capture_output=True, text=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            jar = directory / "audit-summary.jar"
            with zipfile.ZipFile(jar, "w") as archive:
                for path in classes.rglob("*.class"):
                    archive.write(path, path.relative_to(classes))
            result = subprocess.run([
                str(spark / "bin/spark-submit"), "--master", "local[2]",
                "--conf", "spark.ui.enabled=false",
                "--conf", "spark.driver.host=127.0.0.1",
                "--conf", "spark.driver.bindAddress=127.0.0.1",
                "--class", "sfx.AuditDailySummaryCheck", str(jar),
            ], capture_output=True, text=True, timeout=180,
                env={**os.environ, "SPARK_LOCAL_IP": "127.0.0.1"})
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("AUDIT_SUMMARY", result.stdout)
            print(result.stdout.strip())
