package sfx

object TeamGraphComponentsCheck {
  def main(args: Array[String]): Unit = {
    val spark = BatchSupport.session("team-components-check")
    val sc = spark.sparkContext
    try {
      val teams = sc.parallelize(Seq(1L, 2L, 3L, 4L, 5L))
      val members = sc.parallelize(Seq((1L, 3L), (2L, 3L), (3L, 1L), (4L, 1L), (1L, 3L)))
      assert(TeamGraphComponents.components(teams, members).collect().toMap ==
        Map(1L -> 1L, 2L -> 1L, 3L -> 3L, 4L -> 3L, 5L -> 5L))
      val chain = (1L until 9L).flatMap(id => Seq((id, id + 100L), (id + 1L, id + 100L)))
      assert(TeamGraphComponents.components(sc.parallelize(1L to 9L), sc.parallelize(chain))
        .collect().toMap == (1L to 9L).map(_ -> 1L).toMap)
      assert(TeamGraphComponents.components(sc.emptyRDD[Long], sc.emptyRDD[(Long, Long)]).count() == 0)
      println("TEAM_COMPONENTS_CHECK: overlapping identifiers, isolated teams, duplicate memberships, long chain, empty graph: OK")
    } finally {
      spark.stop()
    }
  }
}
