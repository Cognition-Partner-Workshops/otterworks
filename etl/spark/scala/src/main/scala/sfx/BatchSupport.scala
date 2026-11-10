package sfx

import org.apache.spark.sql.{DataFrame, SparkSession}

object BatchSupport {
  def savePartition(frame: DataFrame, area: String, name: String, runDate: String): Unit = {
    require(runDate.matches("\\d{4}-\\d{2}-\\d{2}"), "runDate must be YYYY-MM-DD")
    val path = s"${sys.env.getOrElse("LAKE_DIR", "/opt/lake")}/$area/$name"
    if (frame.isEmpty) {
      frame.write.mode("overwrite").option("partitionOverwriteMode", "static")
        .parquet(s"$path/run_date=$runDate")
    } else {
      frame.withColumn("run_date", org.apache.spark.sql.functions.lit(runDate)).write.mode("overwrite")
        .option("partitionOverwriteMode", "dynamic").partitionBy("run_date").parquet(path)
    }
  }

  def saveJdbcRefresh(frame: DataFrame, table: String): Unit = {
    require(table.matches("[a-zA-Z_][a-zA-Z_0-9]*\\.[a-zA-Z_][a-zA-Z_0-9]*"), "Expected schema.table identifier")
    val url = sys.env.getOrElse("TD_JDBC_URL", "jdbc:postgresql://sfx-tdemu:5432/sfx_teradata")
    val user = sys.env.getOrElse("TD_JDBC_USER", "etl_batch")
    val password = sys.env("TD_JDBC_PASSWORD")
    val stage = table.split("\\.")(0) + "._sfx_stage_" + java.util.UUID.randomUUID().toString.replace("-", "")
    val connection = java.sql.DriverManager.getConnection(url, user, password)
    val statement = connection.createStatement()
    try {
      frame.write.format("jdbc").option("url", url).option("user", user).option("password", password)
        .option("driver", "org.postgresql.Driver").option("dbtable", stage).mode("error").save()
      connection.setAutoCommit(false)
      statement.execute(s"CREATE TABLE IF NOT EXISTS $table (LIKE $stage INCLUDING ALL)")
      statement.execute(s"LOCK TABLE $table IN ACCESS EXCLUSIVE MODE")
      statement.executeUpdate(s"DELETE FROM $table")
      val columns = frame.columns.map(column => "\"" + column.replace("\"", "\"\"") + "\"").mkString(", ")
      statement.executeUpdate(s"INSERT INTO $table ($columns) SELECT $columns FROM $stage")
      connection.commit()
    } catch {
      case error: Exception => connection.rollback(); throw error
    } finally {
      try {
        connection.setAutoCommit(true)
        statement.execute(s"DROP TABLE IF EXISTS $stage")
      } finally {
        statement.close()
        connection.close()
      }
    }
  }

  def session(name: String): SparkSession = SparkSession.builder.appName(name).getOrCreate()

  def landing(spark: SparkSession, area: String, table: String): DataFrame =
    spark.read.option("header", "true").option("sep", "|").option("escape", "\"").option("inferSchema", "true")
      .csv(s"/opt/landing/$area/$table/*.psv")

  def register(spark: SparkSession, area: String, tables: String*): Unit =
    tables.foreach(table => landing(spark, area, table).registerTempTable(table))

  def save(frame: DataFrame, area: String, name: String, table: Option[String] = None): Unit = {
    frame.write.mode("overwrite").parquet(s"/opt/lake/$area/$name")
    table.foreach { target =>
      frame.coalesce(2).write.format("jdbc").mode("overwrite")
        .option("url", sys.env.getOrElse("TD_JDBC_URL", "jdbc:postgresql://sfx-tdemu:5432/sfx_teradata"))
        .option("user", sys.env.getOrElse("TD_JDBC_USER", "etl_batch"))
        .option("password", sys.env("TD_JDBC_PASSWORD"))
        .option("driver", "org.postgresql.Driver").option("dbtable", target).save()
    }
  }
}
