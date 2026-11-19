from pyspark.sql.functions import col, lit

from common.runtime import landing, save, session

spark = session("doc_share_graph_reach")
edges = landing(spark, "DOC_SHARE").select(
    col("OWNER_USER_ID").alias("SOURCE"), col("SHARED_WITH_USER_ID").alias("USER_ID")
).distinct().cache()
visited = spark.createDataFrame([(1, 0)], "USER_ID long, DISTANCE long")
frontier = visited.select("USER_ID")
for depth in range(1, 5):
    frontier = (frontier.withColumnRenamed("USER_ID", "SOURCE").join(edges, "SOURCE")
                .select("USER_ID").distinct()
                .join(visited, "USER_ID", "left_anti").localCheckpoint())
    visited = visited.unionByName(frontier.withColumn("DISTANCE", lit(depth))).localCheckpoint()
save(visited.coalesce(1), "documents", "doc_share_graph_reach")
spark.stop()
