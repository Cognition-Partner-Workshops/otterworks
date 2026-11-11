package sfx

import org.apache.spark.HashPartitioner
import org.apache.spark.rdd.RDD

object TeamGraphComponents {
  def components(teams: RDD[Long], members: RDD[(Long, Long)]): RDD[(Long, Long)] = {
    val partitioner = new HashPartitioner(4)
    val byUser = members.map { case (team, user) => (user, team) }
    val edges = byUser.join(byUser).values.filter { case (a, b) => a != b }
      .distinct().partitionBy(partitioner).cache()
    var labels = teams.union(members.keys).distinct().map(id => (id, id)).partitionBy(partitioner).cache()
    var changed = true
    while (changed) {
      val next = edges.join(labels).map { case (_, (neighbor, component)) => (neighbor, component) }
        .union(labels).reduceByKey(partitioner, (a: Long, b: Long) => math.min(a, b)).cache()
      next.count()
      changed = labels.join(next).filter { case (_, (before, after)) => before != after }.take(1).nonEmpty
      labels.unpersist()
      labels = next
    }
    edges.unpersist()
    labels
  }

  def main(args: Array[String]): Unit = {
    val spark = BatchSupport.session("team_graph_components")
    import spark.implicits._
    val teams = BatchSupport.landing(spark, "users", "TEAM").rdd
      .map(_.getAs[Number]("TEAM_ID").longValue())
    val members = BatchSupport.landing(spark, "users", "TEAM_MEMBER").rdd
      .map(r => (r.getAs[Number]("TEAM_ID").longValue(), r.getAs[Number]("USER_ID").longValue()))
    val labels = components(teams, members)
    BatchSupport.save(labels.toDF("TEAM_ID", "COMPONENT_ID"), "users", "team_graph_components")
    labels.unpersist()
    spark.stop()
  }
}
