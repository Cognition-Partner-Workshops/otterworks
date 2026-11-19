package sfx

import org.apache.spark.sql.functions.{col, udf}
import org.apache.spark.sql.DataFrame
import org.apache.hadoop.fs.Path
import java.time.{LocalDate, ZoneOffset}

object UsersRiskScore {
  def score(users: DataFrame): DataFrame = {
    val risk = udf((logins: Int, actions: Int) =>
      1.0 / (1.0 + math.exp(-(-2.1 + logins * 0.0004 - actions * 0.0001))))
    users.withColumn("RISK_SCORE", risk(col("LOGIN_COUNT"), col("ACTION_COUNT")))
  }

  def saveLake(result: DataFrame, runDate: String): Unit = {
    LocalDate.parse(runDate)
    val root = new Path(s"${sys.env.getOrElse("LAKE_DIR", "/opt/lake")}/users/users_risk_score")
    val fs = root.getFileSystem(result.sparkSession.sparkContext.hadoopConfiguration)
    if (fs.exists(root)) {
      fs.listStatus(root).filterNot(_.getPath.getName.startsWith("run_date=")).foreach { entry =>
        require(fs.delete(entry.getPath, true), s"Could not remove ${entry.getPath}")
      }
    }
    BatchSupport.savePartition(result, "users", "users_risk_score", runDate)
  }

  def main(args: Array[String]): Unit = {
    val spark = BatchSupport.session("users_risk_score")
    try {
      val runDate = sys.env.getOrElse("SFX_RUN_DATE", LocalDate.now(ZoneOffset.UTC).toString)
      LocalDate.parse(runDate)
      val users = BatchSupport.landing(spark, "users", "USER_ACTIVITY_DAILY")
      val result = score(users)
      saveLake(result, runDate)
      BatchSupport.saveJdbcRefresh(result, "sfx_users.SPARK_RISK_SCORE")
    } finally spark.stop()
  }
}
