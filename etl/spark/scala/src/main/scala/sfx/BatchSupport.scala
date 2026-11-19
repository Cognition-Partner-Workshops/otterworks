package sfx

import org.apache.spark.sql.{DataFrame, SparkSession}

object BatchSupport {
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
