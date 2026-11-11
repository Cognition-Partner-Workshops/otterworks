from common.runtime import landing, save, session

spark = session("docs_folder_tree_walk")
parents = landing(spark, "FOLDER").rdd.map(lambda r: (r.FOLDER_ID, r.PARENT_FOLDER_ID))
lookup = spark.sparkContext.broadcast(dict(parents.collect()))
paths = parents.map(lambda r: (r[0], r[0], 0))
for _ in range(20):
    paths = paths.map(lambda r: (r[0], lookup.value.get(r[1]) or r[1], r[2] + int(lookup.value.get(r[1]) is not None)))
result = spark.createDataFrame(paths, "FOLDER_ID long, ROOT_FOLDER_ID long, DEPTH long")
save(result, "documents", "docs_folder_tree_walk")
spark.stop()
