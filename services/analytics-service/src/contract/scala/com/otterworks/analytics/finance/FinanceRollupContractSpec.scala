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
    require(sql == TeradataFinanceRollupRepository.Sql, "Unknown contract query")
    ContractFixtures.read("recorded/teradata/finance-rollups.json")

class EmulatorWarehouse(target: String, asOf: Option[java.time.LocalDate] = None) extends ContractWarehouse:
  def execute(sql: String, status: String, plan: String): Json =
    require(sql == TeradataFinanceRollupRepository.Sql, "Unknown contract query")
    val literal = (value: String) => "'" + value.replace("'", "''") + "'"
    val parts = sql.split("\\?", -1)
    require(parts.length == 3, "Expected two query parameters")
    val unpinned = parts(0) + literal(status) + parts(1) + literal(plan) + parts(2)
    val bound = asOf.fold(unpinned)(date => unpinned.replace("CURRENT_DATE", s"DATE '$date'"))
    val python = sys.env.getOrElse("CONTRACT_KIT_PYTHON", "python3")
    val bridge = sys.env.getOrElse("CONTRACT_KIT_BRIDGE", "../../consumers/contract-kit/bridge.py")
    val command = List(python, bridge, "--target", target, "--query", "finance-rollups") ++
      (if sys.env.get("CONTRACT_RECORD").contains("true") then
        List("--record", "contract/recorded/teradata/finance-rollups.json") else Nil)
    val output = java.nio.file.Files.createTempFile("analytics-contract-", ".json")
    val error = java.nio.file.Files.createTempFile("analytics-contract-", ".log")
    var process: Process = null
    try
      process = new ProcessBuilder(command*).redirectOutput(output.toFile).redirectError(error.toFile).start()
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

class SnowflakeWarehouse extends ContractWarehouse:
  val database = "SFX_D1110_AFTER"
  val schema = "COMPAT"
  val queryTag = """{"run":"sfx-d1110","act":"consumers","consumer":"analytics-service"}"""
  def execute(sql: String, region: String, plan: String): Json =
    val credentials = List("ACCOUNT", "USER", "ROLE", "WAREHOUSE", "PRIVATE_KEY")
      .map(key => sys.env.get("SNOWFLAKE_" + key))
    require(credentials.forall(_.exists(_.nonEmpty)), "Snowflake environment not configured")
    throw new UnsupportedOperationException(
      s"Snowflake JDBC adapter not installed; execute supplied SQL in $database.$schema with QUERY_TAG=$queryTag")

class FinanceRollupContractSpec extends AnyFlatSpec with Matchers:
  "Finance rollups" should "match recorded row counts and aggregates" in {
    val warehouse: ContractWarehouse = sys.env.getOrElse("WAREHOUSE_CONTRACT_TARGET", "teradata-emulator") match
      case "teradata-emulator" => new EmulatorWarehouse("teradata-emulator")
      case "snowflake-semantics" => new EmulatorWarehouse("snowflake-semantics")
      case "replay" => new ReplayWarehouse
      case "snowflake" =>
        val keys = List("ACCOUNT", "USER", "ROLE", "WAREHOUSE", "PRIVATE_KEY")
        if !keys.forall(key => sys.env.get("SNOWFLAKE_" + key).exists(_.nonEmpty)) then
          cancel("Snowflake environment not configured")
        new SnowflakeWarehouse
      case "databricks" => cancel("Databricks target is covered by the live Databricks contract")
      case other => fail(s"Unknown WAREHOUSE_CONTRACT_TARGET: $other")
    val settings = FinanceSettings.load(ConfigFactory.parseResources(
      "com/otterworks/analytics/finance/teradata.conf").resolve())
    val actual = warehouse.execute(TeradataFinanceRollupRepository.Sql, settings.statuses.head, settings.featuredPlan)
    val expected = ContractFixtures.read("expected/finance-rollups.json")
    val rows = actual.hcursor.get[Vector[Vector[Json]]]("rows").toOption.get
    val columns = actual.hcursor.get[Vector[String]]("columns").toOption.get
    rows.size should be > 0
    rows.size shouldBe expected.hcursor.get[Int]("row_count").toOption.get
    actual.hcursor.get[String]("query") shouldBe expected.hcursor.get[String]("query")
    expected.hcursor.downField("sums").focus.get.asObject.get.toMap.foreach { (column, sum) =>
      val index = columns.indexOf(column)
      index should be >= 0
      val total = rows.map(row => BigDecimal(row(index).asString.getOrElse(row(index).noSpaces))).sum
      total shouldBe BigDecimal(sum.asString.get)
    }
  }

  "Finance rollups on Databricks" should "match the Teradata read path on the same live data" in {
    if !sys.env.get("WAREHOUSE_CONTRACT_TARGET").contains("databricks") then
      cancel("WAREHOUSE_CONTRACT_TARGET is not databricks")
    if !List("DATABRICKS_HOST", "DATABRICKS_TOKEN", "DATABRICKS_WAREHOUSE_ID").forall(key => sys.env.get(key).exists(_.nonEmpty)) then
      cancel("Databricks environment not configured")
    given scala.concurrent.ExecutionContext = scala.concurrent.ExecutionContext.global
    val settings = FinanceSettings.load(ConfigFactory.parseResources(
      "com/otterworks/analytics/finance/teradata.conf").resolve())
    val asOf = java.time.LocalDate.parse(sys.env.getOrElse("CONTRACT_AS_OF", "2026-11-09"))
    val step = sys.env.getOrElse("CONTRACT_STEP", "contract")
    val repository = new DatabricksFinanceRollupRepository(asOf = () => asOf, step = step)
    val live = scala.concurrent.Await.result(repository.rollups(settings.statuses.head, settings.featuredPlan),
      scala.concurrent.duration.Duration(5, "minutes"))
    val old = sys.env.get("CONTRACT_OLDPATH") match
      case Some("emulator") => new EmulatorWarehouse("teradata-emulator", Some(asOf))
        .execute(TeradataFinanceRollupRepository.Sql, settings.statuses.head, settings.featuredPlan)
      case _ => ContractFixtures.read("recorded/dbx-d1111-baseline/finance-rollups.json")
    val text = (value: Json) => value.asString.getOrElse(value.noSpaces)
    val oldRows = old.hcursor.get[Vector[Vector[Json]]]("rows").toOption.get.toList.map(row =>
      FinanceRollup(text(row(0)), text(row(1)), text(row(2)), BigDecimal(text(row(3))), BigDecimal(text(row(4))),
        text(row(5)).toLong))
    def summary(rows: List[FinanceRollup]) =
      s"rows=${rows.size} billed=${rows.map(_.billedRevenue).sum} collected=${rows.map(_.collectedCash).sum} " +
        s"active=${rows.map(_.activeAccounts).sum}"
    info(s"as_of=$asOf step=$step databricks: ${summary(live)}")
    info(s"as_of=$asOf teradata old path: ${summary(oldRows)}")
    val expected = ContractFixtures.read("expected/finance-rollups.json")
    withClue(s"databricks ${summary(live)} vs teradata ${summary(oldRows)}: ") {
      live.size should be > 0
      live.size shouldBe expected.hcursor.get[Int]("row_count").toOption.get
      summary(live) shouldBe summary(oldRows)
      live shouldBe oldRows
    }
  }
