package sfx

import org.apache.spark.HashPartitioner

object TeamGraphComponents {
  def main(args: Array[String]): Unit = {
    val spark = BatchSupport.session("team_graph_components")
    import spark.implicits._
    val partitioner = new HashPartitioner(4)
    val members = BatchSupport.landing(spark, "users", "TEAM_MEMBER").rdd
      .map(r => (r.getAs[Int]("TEAM_ID").toLong, r.getAs[Int]("USER_ID").toLong))
    val edges = members.join(members).values.filter { case (a, b) => a != b }
      .partitionBy(partitioner).cache()
    var labels = edges.keys.distinct().map(id => (id, id)).partitionBy(partitioner).cache()
    for (_ <- 0 until 6) {
      val next = edges.join(labels).map { case (_, (neighbor, component)) => (neighbor, component) }
        .union(labels).reduceByKey(partitioner, (a: Long, b: Long) => math.min(a, b)).cache()
      next.count()
      labels.unpersist()
      labels = next
    }
    BatchSupport.save(labels.toDF("USER_ID", "COMPONENT_ID"), "users", "team_graph_components")
    spark.stop()
  }
}
