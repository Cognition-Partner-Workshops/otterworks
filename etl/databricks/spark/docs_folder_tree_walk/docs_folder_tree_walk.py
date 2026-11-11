# run_token=dbx-d1111 expires=2026-11-24
# Serverless PySpark re-expression of etl/spark/jobs/py/docs_folder_tree_walk.py (not deployed: no live parent column).
import argparse

from pyspark.sql import SparkSession, functions as F

JOB = "docs_folder_tree_walk"
STEPS = 20
TARGET = "{catalog}.dbx_d1111_after.documents__spark_docs_folder_tree_walk"


def tag(step):
    return f"/* run=dbx-d1111 act=spark step={step} consumer={JOB} */\n"


def walk(folders, steps=STEPS):
    # Source: parent = lookup.get(cur); cur = parent or cur; depth += parent is not None.
    # A parent of 0 is falsy in Python: depth still increments but the pointer does not move.
    lookup = folders.select(F.col("FOLDER_ID").alias("K"), F.col("PARENT_FOLDER_ID").alias("P")).dropDuplicates(["K"])
    paths = folders.select("FOLDER_ID", F.col("FOLDER_ID").alias("CUR"), F.lit(0).cast("long").alias("DEPTH"))
    for _ in range(steps):
        joined = paths.join(lookup, paths.CUR.eqNullSafe(lookup.K), "left")
        paths = joined.select(
            "FOLDER_ID",
            F.when(F.col("P").isNotNull() & (F.col("P") != 0), F.col("P")).otherwise(F.col("CUR")).alias("CUR"),
            (F.col("DEPTH") + F.when(F.col("P").isNotNull(), 1).otherwise(0)).cast("long").alias("DEPTH"))
    return paths.select("FOLDER_ID", F.col("CUR").alias("ROOT_FOLDER_ID"), "DEPTH")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", default="cpw")
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--step", default="run")
    args = parser.parse_args()
    spark = SparkSession.builder.getOrCreate()
    try:
        aqe = spark.conf.get("spark.sql.adaptive.enabled")
    except Exception as error:  # serverless blocks reading some confs; AQE is on by default there
        aqe = f"not readable ({type(error).__name__}: {str(error).splitlines()[0][:80]})"
    print("spark.sql.adaptive.enabled =", aqe)
    with open(args.inputs) as handle:
        folders = spark.sql(tag(args.step) + handle.read())
    walk(folders).createOrReplaceTempView("docs_folder_tree_walk_result")
    spark.sql(tag(args.step) + f"""CREATE OR REPLACE TABLE {TARGET.format(catalog=args.catalog)}
        COMMENT 'run_token=dbx-d1111 expires=2026-11-24 source=etl/spark/jobs/py/docs_folder_tree_walk.py'
        TBLPROPERTIES ('run_token'='dbx-d1111','expires'='2026-11-24','act'='spark')
        AS SELECT CAST(FOLDER_ID AS BIGINT) AS FOLDER_ID, CAST(ROOT_FOLDER_ID AS BIGINT) AS ROOT_FOLDER_ID, CAST(DEPTH AS BIGINT) AS DEPTH FROM docs_folder_tree_walk_result""")


if __name__ == "__main__":
    main()
