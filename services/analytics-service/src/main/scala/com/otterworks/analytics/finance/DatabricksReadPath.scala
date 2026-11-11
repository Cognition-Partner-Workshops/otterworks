package com.otterworks.analytics.finance

import java.sql.{Connection, DriverManager}
import java.time.{LocalDate, ZoneOffset}
import java.util.Properties
import scala.collection.mutable.ListBuffer
import scala.concurrent.{ExecutionContext, Future, blocking}

/** Live JDBC transport; the consumer migration supplies native queries. */
object DatabricksReadPath:
  def connect(): Connection =
    val host = sys.env("DATABRICKS_HOST").stripPrefix("https://").stripSuffix("/")
    val warehouse = sys.env("DATABRICKS_WAREHOUSE_ID")
    require(host.matches("[a-zA-Z0-9.-]+\\.databricks\\.com"), "Invalid workspace host")
    require(warehouse.matches("[a-f0-9]+"), "Invalid warehouse id")
    val properties = new Properties()
    properties.setProperty("UID", "token")
    properties.setProperty("PWD", sys.env("DATABRICKS_TOKEN"))
    properties.setProperty("EnableArrow", "0")
    DriverManager.getConnection(s"jdbc:databricks://$host:443/default;transportMode=http;ssl=1;AuthMech=3;httpPath=/sql/1.0/warehouses/$warehouse;ConnCatalog=cpw;ConnSchema=dbx_d1111_after", properties)

  def tagged(nativeSql: String, step: String = "contract"): String =
    require(step.matches("[a-z0-9-]+"), "Invalid step")
    s"/* run=dbx-d1111 act=consumers step=$step consumer=analytics-service */\n" + nativeSql

/** Native Databricks SQL for the finance rollups (port of TeradataFinanceRollupRepository.Sql). */
object DatabricksFinanceRollupRepository:
  /** Teradata NOT CASESPECIFIC CHAR/VARCHAR equality: case-insensitive, trailing pads ignored. */
  private def teradataEquals(left: String, right: String): String = s"upper(rtrim($left)) = upper(rtrim($right))"

  val Sql: String =
    s"""WITH bounds AS (
      | SELECT trunc(CAST(? AS DATE), 'MM') AS M0
      |), months AS (
      | SELECT add_months(b.M0, -t.N) AS MONTH_START FROM bounds b LATERAL VIEW explode(sequence(0, 11)) t AS N
      |), selected_subscriptions AS (
      | SELECT DISTINCT s.SUBSCRIPTION_ID, s.CUSTOMER_ID, p.PLAN_NAME
      | FROM billing__subscription s JOIN billing__plan_catalog p ON ${teradataEquals("p.PLAN_CODE", "s.PLAN_CODE")}
      | WHERE ${teradataEquals("s.STATUS_CD", "?")} AND ${teradataEquals("s.PLAN_CODE", "?")}
      |), accounts AS (
      | SELECT DISTINCT c.CUSTOMER_ID, c.REGION_CD, c.STATUS_CD, c.CREATED_DT, s.PLAN_NAME
      | FROM billing__customer_account c JOIN selected_subscriptions s ON s.CUSTOMER_ID = c.CUSTOMER_ID
      |), billed AS (
      | SELECT i.CUSTOMER_ID, year(i.INVOICE_DT) * 100 + month(i.INVOICE_DT) AS PERIOD_ID,
      | SUM(i.SUBTOTAL_AMOUNT) AS REVENUE FROM billing__invoice_hdr i
      | JOIN selected_subscriptions s ON s.SUBSCRIPTION_ID = i.SUBSCRIPTION_ID CROSS JOIN bounds b
      | WHERE i.INVOICE_DT >= add_months(b.M0, -11) AND i.INVOICE_DT < add_months(b.M0, 1)
      | GROUP BY 1, 2
      |), cash AS (
      | SELECT p.CUSTOMER_ID, year(p.PAYMENT_DT) * 100 + month(p.PAYMENT_DT) AS PERIOD_ID,
      | SUM(p.AMOUNT) AS COLLECTED FROM billing__payment p
      | JOIN billing__invoice_hdr i ON i.INVOICE_ID = p.INVOICE_ID
      | JOIN selected_subscriptions s ON s.SUBSCRIPTION_ID = i.SUBSCRIPTION_ID CROSS JOIN bounds b
      | WHERE p.PAYMENT_DT >= add_months(b.M0, -11) AND p.PAYMENT_DT < add_months(b.M0, 1)
      | GROUP BY 1, 2
      |)
      |SELECT date_format(m.MONTH_START, 'yyyy-MM') AS MONTH_LABEL, a.REGION_CD, a.PLAN_NAME,
      | coalesce(SUM(b.REVENUE), 0) AS BILLED_REVENUE, coalesce(SUM(p.COLLECTED), 0) AS COLLECTED_CASH,
      | SUM(CASE WHEN ${teradataEquals("a.STATUS_CD", "'ACTIVE'")} AND a.CREATED_DT < add_months(m.MONTH_START, 1)
      | THEN 1 ELSE 0 END) AS ACTIVE_ACCOUNTS
      |FROM months m CROSS JOIN accounts a
      |LEFT JOIN billed b ON b.CUSTOMER_ID = a.CUSTOMER_ID
      | AND b.PERIOD_ID = year(m.MONTH_START) * 100 + month(m.MONTH_START)
      |LEFT JOIN cash p ON p.CUSTOMER_ID = a.CUSTOMER_ID
      | AND p.PERIOD_ID = year(m.MONTH_START) * 100 + month(m.MONTH_START)
      |GROUP BY 1, 2, 3 ORDER BY 1, 2, 3""".stripMargin

class DatabricksFinanceRollupRepository(connect: () => Connection = () => DatabricksReadPath.connect(),
                                        asOf: () => LocalDate = () => LocalDate.now(ZoneOffset.UTC),
                                        step: String = "contract")(using ec: ExecutionContext)
    extends FinanceRollupRepository:
  override def rollups(status: String, plan: String): Future[List[FinanceRollup]] = Future {
    blocking {
      val connection = connect()
      try
        val statement = connection.prepareStatement(DatabricksReadPath.tagged(DatabricksFinanceRollupRepository.Sql, step))
        try
          statement.setString(1, asOf().toString)
          statement.setString(2, status)
          statement.setString(3, plan)
          val rs = statement.executeQuery()
          try
            val rows = ListBuffer.empty[FinanceRollup]
            while rs.next() do
              rows += FinanceRollup(rs.getString("MONTH_LABEL"), rs.getString("REGION_CD"),
                rs.getString("PLAN_NAME"), BigDecimal(rs.getBigDecimal("BILLED_REVENUE")),
                BigDecimal(rs.getBigDecimal("COLLECTED_CASH")), rs.getLong("ACTIVE_ACCOUNTS"))
            rows.toList
          finally rs.close()
        finally statement.close()
      finally connection.close()
    }
  }
