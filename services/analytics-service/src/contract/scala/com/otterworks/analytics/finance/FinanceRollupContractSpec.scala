package com.otterworks.analytics.finance

import com.typesafe.config.ConfigFactory
import io.circe.{Json, parser}
import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers
import scala.io.Source

trait ContractWarehouse:
  def execute(sql: String, region: String, plan: String): Json

object ContractFixtures:
  def read(path: String): Json =
    val source = Source.fromFile("contract/" + path)
    try parser.parse(source.mkString).fold(throw _, identity)
    finally source.close()

class ReplayWarehouse extends ContractWarehouse:
  def execute(sql: String, status: String, plan: String): Json =
    require(sql == LegacyFinanceRollupSql.Sql, "Unknown contract query")
    ContractFixtures.read("recorded/teradata/finance-rollups.json")

class EmulatorWarehouse(target: String) extends ContractWarehouse:
  def execute(sql: String, status: String, plan: String): Json =
    require(sql == LegacyFinanceRollupSql.Sql, "Unknown contract query")
    val literal = (value: String) => "'" + value.replace("'", "''") + "'"
    val parts = sql.split("\\?", -1)
    require(parts.length == 3, "Expected two query parameters")
    val bound = parts(0) + literal(status) + parts(1) + literal(plan) + parts(2)
    val python = sys.env.getOrElse("CONTRACT_KIT_PYTHON", "python3")
    val bridge = sys.env.getOrElse("CONTRACT_KIT_BRIDGE", "../../consumers/contract-kit/bridge.py")
    val command = List(python, bridge, "--target", target, "--query", "finance-rollups") ++
      (if sys.env.get("CONTRACT_RECORD").contains("true") then
        List("--record", "contract/recorded/teradata/finance-rollups.json") else Nil)
    val output = java.nio.file.Files.createTempFile("analytics-contract-", ".json")
    val error = java.nio.file.Files.createTempFile("analytics-contract-", ".log")
    var process: Process = null
    try
      val builder = new ProcessBuilder(command*).redirectOutput(output.toFile).redirectError(error.toFile)
      builder.environment().put("TD_USER", "svc_exit_parity")
      EmulatorEnvironment.configure(builder)
      builder.command().set(0, builder.environment().getOrDefault("CONTRACT_KIT_PYTHON", python))
      process = builder.start()
      val input = process.getOutputStream
      try input.write(bound.getBytes(java.nio.charset.StandardCharsets.UTF_8))
      finally input.close()
      require(process.waitFor(60, java.util.concurrent.TimeUnit.SECONDS), "Contract bridge timed out")
      require(process.exitValue() == 0, java.nio.file.Files.readString(error))
      parser.parse(java.nio.file.Files.readString(output)).fold(throw _, identity)
    finally
      if process != null && process.isAlive then process.destroyForcibly()
      java.nio.file.Files.deleteIfExists(output)
      java.nio.file.Files.deleteIfExists(error)

object EmulatorEnvironment:
  private lazy val bootstrap: Map[String, String] =
    import scala.sys.process.*
    val output = Process(List("bash", "contract/start-emulator.sh")).!!
    output.linesIterator.filter(_.startsWith("CONTRACT_ENV ")).map { line =>
      val Array(key, value) = line.stripPrefix("CONTRACT_ENV ").split("=", 2): @unchecked
      key -> value
    }.toMap

  def available: Boolean =
    val socket = new java.net.Socket()
    try
      socket.connect(new java.net.InetSocketAddress(
        sys.env.getOrElse("TD_PG_HOST", "localhost"),
        sys.env.getOrElse("TD_PG_PORT", "5432").toInt), 500)
      true
    catch case _: java.io.IOException => false
    finally socket.close()

  def configure(builder: ProcessBuilder): Unit =
    if !available && sys.env.get("CI").contains("true") then
      bootstrap.foreach((key, value) => builder.environment().put(key, value))

class SnowflakeWarehouse extends ContractWarehouse:
  def execute(sql: String, status: String, plan: String): Json =
    import scala.concurrent.{Await, ExecutionContext}
    import scala.concurrent.duration.*
    given ExecutionContext = ExecutionContext.global
    val settings = FinanceSettings.load(ConfigFactory.parseResources(
      "com/otterworks/analytics/finance/snowflake.conf").resolve())
    val repository = new SnowflakeFinanceRollupRepository(() => {
      val connection = SnowflakeFinanceRollupRepository.connect(settings)
      try
        val statement = connection.createStatement()
        try
          List("TIMEZONE" -> "UTC", "QUERY_TAG" -> SnowflakeFinanceRollupRepository.QueryTag).foreach { (name, expected) =>
            val result = statement.executeQuery(s"SHOW PARAMETERS LIKE '$name' IN SESSION")
            try
              require(result.next(), s"Missing session parameter: $name")
              val value = result.getString("value")
              require(value == expected, s"Unexpected session $name: $value")
              println(s"Snowflake session $name=$value (assertion passed)")
            finally result.close()
          }
        finally statement.close()
        connection
      catch
        case error: Throwable =>
          connection.close()
          throw error
    })
    val rows = Await.result(repository.rollups(status, plan), 3.minutes)
    repository.queryIds.foreach(id => println(s"Snowflake query ID: $id"))
    Json.obj("query" -> Json.fromString("finance-rollups"),
      "columns" -> Json.arr(List("MONTH_LABEL", "REGION_CD", "PLAN_NAME",
        "BILLED_REVENUE", "COLLECTED_CASH", "ACTIVE_ACCOUNTS").map(Json.fromString)*),
      "rows" -> Json.arr(rows.map(row => Json.arr(
        Json.fromString(row.month), Json.fromString(row.region), Json.fromString(row.plan),
        Json.fromString(row.billedRevenue.toString), Json.fromString(row.collectedCash.toString),
        Json.fromLong(row.activeAccounts)))*))

class FinanceRollupContractSpec extends AnyFlatSpec with Matchers:
  "Finance rollups" should "match recorded row counts and aggregates" in {
    val warehouse: ContractWarehouse = sys.env.getOrElse("WAREHOUSE_CONTRACT_TARGET", "teradata-emulator") match
      case "teradata-emulator" => new EmulatorWarehouse("teradata-emulator")
      case "snowflake-semantics" => new EmulatorWarehouse("snowflake-semantics")
      case "replay" => new ReplayWarehouse
      case "snowflake" =>
        val keys = List("ACCOUNT", "USER", "ROLE", "PRIVATE_KEY")
        if !keys.forall(key => sys.env.get("SNOWFLAKE_" + key).exists(_.nonEmpty)) then
          cancel("Snowflake environment not configured")
        new SnowflakeWarehouse
      case other => fail(s"Unknown WAREHOUSE_CONTRACT_TARGET: $other")
    val settings = FinanceSettings.load(ConfigFactory.parseResources(
      "com/otterworks/analytics/finance/snowflake.conf").resolve())
    val actual = warehouse.execute(LegacyFinanceRollupSql.Sql, settings.statuses.head, settings.featuredPlan)
    val rows = actual.hcursor.get[Vector[Vector[Json]]]("rows").toOption.get
    val columns = actual.hcursor.get[Vector[String]]("columns").toOption.get
    rows.size should be > 0
    if sys.env.get("WAREHOUSE_CONTRACT_TARGET").contains("snowflake") then
      val recorded = ContractFixtures.read("recorded/teradata/finance-rollups.json")
      columns shouldBe recorded.hcursor.get[Vector[String]]("columns").toOption.get
      val referenceRows = recorded.hcursor.get[Vector[Vector[Json]]]("rows").toOption.get
      List("MONTH_LABEL", "PLAN_NAME").foreach { column =>
        val index = columns.indexOf(column)
        rows.map(_(index)).toSet shouldBe referenceRows.map(_(index)).toSet
      }
      println(s"Snowflake contract: ${rows.size} rows; columns, month labels and plan names match replay")
    else
      assertAggregates(actual)
  }

  private def assertAggregates(actual: Json): Unit =
    val expected = ContractFixtures.read("expected/finance-rollups.json")
    val rows = actual.hcursor.get[Vector[Vector[Json]]]("rows").toOption.get
    val columns = actual.hcursor.get[Vector[String]]("columns").toOption.get
    rows.size shouldBe expected.hcursor.get[Int]("row_count").toOption.get
    actual.hcursor.get[String]("query") shouldBe expected.hcursor.get[String]("query")
    expected.hcursor.downField("sums").focus.get.asObject.get.toMap.foreach { (column, sum) =>
      val index = columns.indexOf(column)
      index should be >= 0
      val total = rows.map(row => BigDecimal(row(index).asString.getOrElse(row(index).noSpaces))).sum
      total shouldBe BigDecimal(sum.asString.get)
    }

  "Case comparison" should "preserve subscription filters under Snowflake semantics" in {
    if !EmulatorEnvironment.available && !sys.env.get("CI").contains("true") then
      cancel("Teradata emulator not configured")
    val settings = FinanceSettings.load(ConfigFactory.parseResources(
      "com/otterworks/analytics/finance/snowflake.conf").resolve())
    val actual = new EmulatorWarehouse("snowflake-semantics")
      .execute(LegacyFinanceRollupSql.Sql, settings.statuses.head, settings.featuredPlan)
    actual.hcursor.get[Vector[Vector[Json]]]("rows").toOption.get.size should be > 0
    assertAggregates(actual)
  }
