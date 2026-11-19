package sfx

import org.apache.spark.sql.functions.{col, udf}

object UsersRiskScore {
  def main(args: Array[String]): Unit = {
    val spark = BatchSupport.session("users_risk_score")
    val users = BatchSupport.landing(spark, "users", "USER_ACTIVITY_DAILY")
    val score = udf((logins: Int, actions: Int) =>
      1.0 / (1.0 + math.exp(-(-2.1 + logins * 0.0004 - actions * 0.0001))))
    val result = users.withColumn("RISK_SCORE", score(col("LOGIN_COUNT"), col("ACTION_COUNT")))
    BatchSupport.save(result, "users", "users_risk_score", Some("sfx_users.SPARK_RISK_SCORE"))
    spark.stop()
  }
}
