"""Exercise local Spark on generated text, not a billing port."""

import os
from pathlib import Path
import subprocess
import tempfile

from pyspark.sql import SparkSession

from harness import ESTATE, environment


def main():
    output = ESTATE / "reports/spark"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output) as directory:
        root = Path(directory)
        subprocess.run(["perl", str(ESTATE / "tools/gen_sample_data.pl"), "smoke", "1", "8"],
                       env=environment(root), check=True)
        spark = SparkSession.builder.master("local[*]").appName("custbill-smoke").getOrCreate()
        try:
            count = spark.read.text(str(root / "sftp-drop/upload/CUSTBILL_SMOKE_001.dat")).count()
            java = spark.sparkContext._jvm.java.lang.System.getProperty("java.version")
            print(f"Spark {spark.version}; Java {java}; Python {os.sys.version.split()[0]}; "
                  f"master={spark.sparkContext.master}")
            assert count == 10, count
            print(f"spark smoke: PASS; generated .dat rows={count} (8 data + HDR + TRL)")
        finally:
            spark.stop()


if __name__ == "__main__":
    main()
