# run_token=dbx-d1111 expires=2026-11-24
# Serverless PySpark port of etl/spark/jobs/py/docs_tag_normalize.py.
import argparse
import re

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, udf
from pyspark.sql.types import StringType

JOB = "docs_tag_normalize"
COLUMNS = "DOC_TAG_ID BIGINT, DOCUMENT_ID BIGINT, TAG STRING, NORMALIZED_TAG STRING"
SELECT = ", ".join(f"CAST({name} AS {kind}) AS {name}" for name, kind in (c.strip().split(" ") for c in COLUMNS.split(",")))


def normalize_tag(tag):
    return re.sub(r"\s+", "-", (tag or "").strip().lower())


def transform(frame):
    return frame.withColumn("NORMALIZED_TAG", udf(normalize_tag, StringType())(col("TAG")))


def prefix(step):
    return f"/* run=dbx-d1111 act=spark step={step} consumer={JOB} */\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--step", default="run")
    args = parser.parse_args()

    spark = SparkSession.builder.getOrCreate()
    try:
        adaptive = spark.sql("SET spark.sql.adaptive.enabled").collect()[0][1]
    except Exception as error:
        adaptive = f"unavailable ({type(error).__name__})"
    print(f"spark.sql.adaptive.enabled={adaptive}")

    with open(args.inputs) as handle:
        source = spark.sql(handle.read())
    transform(source).createOrReplaceTempView("docs_tag_normalize_result")
    spark.sql(
        prefix(args.step)
        + f"CREATE OR REPLACE TABLE {args.target}\n"
        + "COMMENT 'Migrated Spark job docs_tag_normalize. run_token=dbx-d1111 expires=2026-11-24'\n"
        + "TBLPROPERTIES ('run_token'='dbx-d1111','expires'='2026-11-24','act'='spark')\n"
        + f"AS SELECT {SELECT} FROM docs_tag_normalize_result"
    )
    count = spark.table(args.target).count()
    print(f"target={args.target} rows={count}")


if __name__ == "__main__":
    main()
