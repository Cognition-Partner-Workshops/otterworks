# run_token=dbx-d1111 expires=2026-11-24
# Serverless PySpark re-expression of etl/spark/jobs/py/doc_share_graph_reach.py.
import argparse

from pyspark.sql import SparkSession, functions as F

JOB = "doc_share_graph_reach"
START_USER = 1
MAX_DEPTH = 4
TARGET = "{catalog}.dbx_d1111_after.documents__spark_doc_share_graph_reach"


def tag(step):
    return f"/* run=dbx-d1111 act=spark step={step} consumer={JOB} */\n"


def reach(spark, shares, start=START_USER, max_depth=MAX_DEPTH):
    # RDD join / subtractByKey match None keys, hence null-safe equality.
    edges = shares.select(F.col("OWNER_USER_ID").alias("SRC"), F.col("SHARED_WITH_USER_ID").alias("DST")).distinct()
    frontier = spark.createDataFrame([(start, 0)], "USER_ID long, DISTANCE long")
    visited = frontier
    for depth in range(1, max_depth + 1):
        reached = (frontier.alias("f").join(edges.alias("e"), F.col("f.USER_ID").eqNullSafe(F.col("e.SRC")))
                   .select(F.col("e.DST").alias("NODE")).distinct())
        frontier = (reached.join(visited.alias("v"), F.col("NODE").eqNullSafe(F.col("v.USER_ID")), "left_anti")
                    .select(F.col("NODE").alias("USER_ID"), F.lit(depth).cast("long").alias("DISTANCE")))
        visited = visited.unionByName(frontier).groupBy("USER_ID").agg(F.min("DISTANCE").alias("DISTANCE"))
    return visited


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
        shares = spark.sql(tag(args.step) + handle.read())
    reach(spark, shares).createOrReplaceTempView("doc_share_graph_reach_result")
    spark.sql(tag(args.step) + f"""CREATE OR REPLACE TABLE {TARGET.format(catalog=args.catalog)}
        COMMENT 'run_token=dbx-d1111 expires=2026-11-24 source=etl/spark/jobs/py/doc_share_graph_reach.py'
        TBLPROPERTIES ('run_token'='dbx-d1111','expires'='2026-11-24','act'='spark')
        AS SELECT CAST(USER_ID AS BIGINT) AS USER_ID, CAST(DISTANCE AS BIGINT) AS DISTANCE FROM doc_share_graph_reach_result""")


if __name__ == "__main__":
    main()
