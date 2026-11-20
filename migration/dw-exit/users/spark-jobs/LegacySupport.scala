package sfx

import org.apache.spark.sql.{DataFrame, SparkSession}

// Local I/O adapter; the legacy job bodies are compiled without modification.
object BatchSupport {
  def session(name: String): SparkSession = SparkSession.builder.appName(name).getOrCreate()
  def landing(spark: SparkSession, area: String, table: String): DataFrame =
    spark.read.parquet(s"${sys.env("USERS_PARITY_WORK")}/inputs/$table")
  def save(frame: DataFrame, area: String, name: String, table: Option[String] = None): Unit =
    frame.write.mode("overwrite").parquet(s"${sys.env("USERS_PARITY_WORK")}/legacy/$name")
}
