# run_token=dbx-d1111 expires=2026-11-24
# Serverless PySpark re-expression of etl/spark/scala/src/main/scala/sfx/TeamGraphComponents.scala.
import argparse

from pyspark.sql import SparkSession, functions as F

JOB = "team_graph_components"
ITERATIONS = 6
TARGET = "{catalog}.dbx_d1111_after.users__spark_team_graph_components"


def tag(step):
    return f"/* run=dbx-d1111 act=spark step={step} consumer={JOB} */\n"


def components(members, iterations=ITERATIONS):
    # Scala getAs[Int] unboxes NULL to 0.
    pairs = members.select(F.coalesce(F.col("TEAM_ID").cast("bigint"), F.lit(0)).alias("TEAM_ID"),
                           F.coalesce(F.col("USER_ID").cast("bigint"), F.lit(0)).alias("USER_ID"))
    left, right = pairs.alias("l"), pairs.alias("r")
    edges = (left.join(right, F.col("l.TEAM_ID") == F.col("r.TEAM_ID"))
             .select(F.col("l.USER_ID").alias("SRC"), F.col("r.USER_ID").alias("DST"))
             .where(F.col("SRC") != F.col("DST")).distinct())
    nodes = edges.select("SRC").distinct()
    # edges.join(labels) ∪ labels == closed neighbourhood join, so each round references labels once.
    closed = edges.unionByName(nodes.select("SRC", F.col("SRC").alias("DST")))
    labels = nodes.select(F.col("SRC").alias("USER_ID"), F.col("SRC").alias("COMPONENT_ID"))
    for _ in range(iterations):
        labels = (closed.join(labels, closed.SRC == labels.USER_ID)
                  .groupBy(F.col("DST").alias("USER_ID")).agg(F.min("COMPONENT_ID").alias("COMPONENT_ID")))
    return labels.select("USER_ID", "COMPONENT_ID")


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
        members = spark.sql(tag(args.step) + handle.read())
    components(members).createOrReplaceTempView("team_graph_components_result")
    spark.sql(tag(args.step) + f"""CREATE OR REPLACE TABLE {TARGET.format(catalog=args.catalog)}
        COMMENT 'run_token=dbx-d1111 expires=2026-11-24 source=etl/spark/scala/src/main/scala/sfx/TeamGraphComponents.scala'
        TBLPROPERTIES ('run_token'='dbx-d1111','expires'='2026-11-24','act'='spark')
        AS SELECT CAST(USER_ID AS BIGINT) AS USER_ID, CAST(COMPONENT_ID AS BIGINT) AS COMPONENT_ID FROM team_graph_components_result""")


if __name__ == "__main__":
    main()
