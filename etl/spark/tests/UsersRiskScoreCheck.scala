package sfx

import org.apache.spark.sql.SparkSession
import org.apache.spark.sql.functions.col

object UsersRiskScoreCheck {
  def main(args: Array[String]): Unit = {
    val spark = SparkSession.builder.appName("users-risk-score-check").getOrCreate()
    import spark.implicits._
    try {
      val input = Seq((1L, 7, 90), (2L, 0, 0)).toDF("USER_ID", "LOGIN_COUNT", "ACTION_COUNT")
      val scored = UsersRiskScore.score(input)
      val rows = scored.orderBy("USER_ID").collect()
      assert(rows.length == 2)
      assert(rows(0).getDouble(3) == 1.0 / (1.0 + math.exp(-(-2.1 + 7 * 0.0004 - 90 * 0.0001))))
      assert(rows(1).getDouble(3) == 1.0 / (1.0 + math.exp(2.1)))
      val root = sys.env("LAKE_DIR") + "/users/users_risk_score"
      scored.write.mode("overwrite").parquet(root)
      UsersRiskScore.saveLake(scored, "2026-11-18")
      UsersRiskScore.saveLake(scored, "2026-11-19")
      UsersRiskScore.saveLake(scored, "2026-11-19")
      assert(spark.read.parquet(root).count() == 4)
      UsersRiskScore.saveLake(scored.limit(0), "2026-11-19")
      assert(spark.read.parquet(root).count() == 2)
      assert(spark.read.parquet(root + "/run_date=2026-11-19").count() == 0)
      assert(UsersRiskScore.score(input.limit(0)).count() == 0)
      try {
        UsersRiskScore.saveLake(scored, "invalid")
        sys.error("Expected invalid date to fail")
      } catch { case _: java.time.format.DateTimeParseException => () }
      assert(spark.read.parquet(root).count() == 2)
      try {
        UsersRiskScore.score(input.drop("LOGIN_COUNT"))
        sys.error("Expected missing column to fail")
      } catch { case _: org.apache.spark.sql.AnalysisException => () }
      println("USERS_RISK_SCORE scoring, legacy cleanup, reruns, date retention, empty and error cases: OK")
    } finally spark.stop()
  }
}
