package sfx

import org.apache.spark.HashPartitioner
import org.apache.spark.sql.DataFrame
import org.apache.spark.sql.functions.col

object TeamGraphComponents {
  def main(args: Array[String]): Unit = {
    val spark = BatchSupport.session("team_graph_components")
    val runDate = sys.env.getOrElse("SFX_RUN_DATE", java.time.LocalDate.now(java.time.ZoneOffset.UTC).toString)
    val result = transform(BatchSupport.landing(spark, "users", "TEAM_MEMBER"))
    BatchSupport.savePartition(result, "users", "team_graph_components", runDate)
    spark.stop()
  }

  def transform(frame: DataFrame): DataFrame = {
    val spark = frame.sparkSession
    import spark.implicits._
    val partitioner = new HashPartitioner(math.max(1, frame.rdd.getNumPartitions / 2))
    val members = frame.withColumn("TEAM_ID", col("TEAM_ID").cast("long"))
      .withColumn("USER_ID", col("USER_ID").cast("long")).rdd
      .map(r => (r.getAs[Long]("TEAM_ID"), r.getAs[Long]("USER_ID")))
    val edges = members.join(members, partitioner).values.filter { case (a, b) => a != b }
      .partitionBy(partitioner).cache()
    var labels = edges.keys.distinct().map(id => (id, id)).partitionBy(partitioner).cache()
    var iteration = 0
    var changed = true
    while (iteration < 6 && changed) {
      val next = edges.join(labels).map { case (_, (neighbor, component)) => (neighbor, component) }
        .union(labels).reduceByKey(partitioner, (a: Long, b: Long) => math.min(a, b)).cache()
      changed = !next.join(labels).filter { case (_, (current, previous)) => current != previous }.isEmpty()
      labels.unpersist()
      labels = next
      iteration += 1
    }
    labels.toDF("USER_ID", "COMPONENT_ID")
  }
}
