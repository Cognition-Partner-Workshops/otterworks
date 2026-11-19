package sfx

import org.apache.spark.sql.AnalysisException

object TeamGraphComponentsCheck {
  def main(args: Array[String]): Unit = {
    val spark = BatchSupport.session("team-components-check")
    import spark.implicits._
    try {
      def check(members: Seq[(Long, Long)]): Unit = {
        val edges = for ((team, user) <- members; (otherTeam, neighbor) <- members
                         if team == otherTeam && user != neighbor) yield (user, neighbor)
        var expected = edges.map { case (user, _) => user -> user }.toMap
        for (_ <- 0 until 6) {
          val previous = expected
          expected = edges.foldLeft(previous) { case (labels, (user, neighbor)) =>
            labels.updated(neighbor, math.min(labels(neighbor), previous(user)))
          }
        }
        val result = TeamGraphComponents.transform(members.toDF("TEAM_ID", "USER_ID")).collect()
        assert(result.map(row => row.getLong(0) -> row.getLong(1)).toMap == expected)
        assert(result.length == expected.size)
      }
      check(Seq((1L, 3L), (1L, 4L), (2L, 4L), (2L, 5L), (1L, 3L), (3L, 99L)))
      check((1L until 10L).flatMap(team => Seq((team, team), (team, team + 1L))))
      check(Seq((1L, 1L), (1L, 2L), (2L, 3L), (2L, 4L)))
      check(Seq.empty[(Long, Long)])
      var rejected = false
      try TeamGraphComponents.transform(spark.emptyDataFrame) catch {
        case _: AnalysisException => rejected = true
      }
      assert(rejected)
      println("TEAM_COMPONENTS_CHECK: exact six-round reference, overlaps, duplicates, isolated users, long chain, disconnected graph, empty and invalid inputs: OK")
    } finally {
      spark.stop()
    }
  }
}
