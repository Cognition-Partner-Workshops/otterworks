from common.runtime import landing, save, session

spark = session("doc_share_graph_reach")
edges = landing(spark, "DOC_SHARE").rdd.map(lambda r: (r.OWNER_USER_ID, r.SHARED_WITH_USER_ID)).cache()
frontier = spark.sparkContext.parallelize([(1, 0)], 2)
visited = frontier
for depth in range(1, 5):
    frontier = frontier.join(edges).map(lambda r: (r[1][1], depth)).subtractByKey(visited).cache()
    visited = visited.union(frontier).reduceByKey(min)
result = spark.createDataFrame(visited, "USER_ID long, DISTANCE long")
save(result, "documents", "doc_share_graph_reach")
spark.stop()
