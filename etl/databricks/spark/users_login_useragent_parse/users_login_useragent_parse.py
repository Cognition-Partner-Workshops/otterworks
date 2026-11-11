# run_token=dbx-d1111 expires=2026-11-24
# Serverless PySpark port of etl/spark/jobs/py/users_login_useragent_parse.py.
import argparse
import re

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lit, udf
from pyspark.sql.types import StringType

JOB = "users_login_useragent_parse"
COLUMNS = "LOGIN_EVENT_ID BIGINT, USER_ID BIGINT, EVENT_AT TIMESTAMP, IP_ADDRESS STRING, USER_AGENT STRING, RAW_LINE STRING, BROWSER STRING"
SELECT = ", ".join(f"CAST({name} AS {kind}) AS {name}" for name, kind in (c.strip().split(" ") for c in COLUMNS.split(",")))

def browser(agent):
    match = re.search(r"(Chrome|Firefox|Safari)/(\S+)", agent or "")
    return match.group(1) + "/" + match.group(2) if match else "Other"


def transform(frame):
    return frame.withColumn("BROWSER", udf(browser, StringType())(col("USER_AGENT")))


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
        + "COMMENT 'Migrated Spark job users_login_useragent_parse. run_token=dbx-d1111 expires=2026-11-24'\n"
        + "TBLPROPERTIES ('run_token'='dbx-d1111','expires'='2026-11-24','act'='spark')\n"
        + f"AS SELECT {SELECT} FROM result"
    )
    print(f"target={args.target} rows={spark.table(args.target).count()}")


if __name__ == "__main__":
    main()
