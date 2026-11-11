# run_token=dbx-d1111 expires=2026-11-24
# Serverless PySpark port of etl/spark/jobs/py/user_pref_json_flatten.py.
import argparse
import json

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lit, udf
from pyspark.sql.types import StringType

JOB = "user_pref_json_flatten"
COLUMNS = "USER_PREF_ID BIGINT, USER_ID BIGINT, PREF_JSON STRING, THEME STRING, NOTIFICATIONS STRING, LOCALE STRING"
SELECT = ", ".join(f"CAST({name} AS {kind}) AS {name}" for name, kind in (c.strip().split(" ") for c in COLUMNS.split(",")))

KEYS = ("theme", "notifications", "locale")


def preference(raw, key):
    try:
        return str(json.loads(raw or "{}").get(key, ""))
    except (ValueError, TypeError):
        return None


def transform(frame):
    extract = udf(preference, StringType())
    for key in KEYS:
        frame = frame.withColumn(key.upper(), extract(col("PREF_JSON"), lit(key)))
    return frame


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
    transform(source).createOrReplaceTempView("result")
    spark.sql(
        prefix(args.step)
        + f"CREATE OR REPLACE TABLE {args.target}\n"
        + "COMMENT 'Migrated Spark job user_pref_json_flatten. run_token=dbx-d1111 expires=2026-11-24'\n"
        + "TBLPROPERTIES ('run_token'='dbx-d1111','expires'='2026-11-24','act'='spark')\n"
        + f"AS SELECT {SELECT} FROM result"
    )
    print(f"target={args.target} rows={spark.table(args.target).count()}")


if __name__ == "__main__":
    main()
