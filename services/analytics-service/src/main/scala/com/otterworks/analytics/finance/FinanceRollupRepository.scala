package com.otterworks.analytics.finance

import com.typesafe.config.Config
import java.sql.{Connection, DriverManager}
import scala.concurrent.{ExecutionContext, Future, blocking}
import scala.collection.mutable.ListBuffer

case class FinanceRollup(month: String, region: String, plan: String,
                         billedRevenue: BigDecimal, collectedCash: BigDecimal, activeAccounts: Long)

trait FinanceRollupRepository:
  def rollups(status: String, plan: String): Future[List[FinanceRollup]]

case class FinanceSettings(enabled: Boolean, statuses: List[String], featuredPlan: String,
                           url: String, user: String, password: String)

object FinanceSettings:
  def load(config: Config): FinanceSettings =
    import scala.jdk.CollectionConverters.*
    val c = config.getConfig("finance.warehouse")
    FinanceSettings(c.getBoolean("enabled"), c.getStringList("statuses").asScala.toList,
      c.getString("featured-plan"), c.getString("url"), c.getString("user"), c.getString("password"))

object TeradataFinanceRollupRepository:
  private val offsets = (0 until 12).map(n => s"SEL $n AS N").mkString(" UNION ALL ")
  val Sql: String =
    s"""WITH months AS (
       | SEL TOP 12 ADD_MONTHS(CURRENT_DATE - CAST(EXTRACT(DAY FROM CURRENT_DATE) AS INTEGER) + 1, -N) AS MONTH_START
       | FROM ($offsets) offsets
       |), selected_subscriptions AS (
       | SEL DISTINCT s.SUBSCRIPTION_ID, s.CUSTOMER_ID, p.PLAN_NAME
       | FROM SFX_BILLING.SUBSCRIPTION s JOIN SFX_BILLING.PLAN_CATALOG p ON p.PLAN_CODE = s.PLAN_CODE
       | WHERE s.STATUS_CD = ? AND s.PLAN_CODE = ?
       |), accounts AS (
       | SEL DISTINCT c.CUSTOMER_ID, c.REGION_CD, c.STATUS_CD, c.CREATED_DT, s.PLAN_NAME
       | FROM SFX_BILLING.CUSTOMER_ACCOUNT c JOIN selected_subscriptions s ON s.CUSTOMER_ID = c.CUSTOMER_ID
       |), billed AS (
       | SEL i.CUSTOMER_ID, EXTRACT(YEAR FROM i.INVOICE_DT) * 100 + EXTRACT(MONTH FROM i.INVOICE_DT) AS PERIOD_ID,
       | SUM(i.SUBTOTAL_AMOUNT) AS REVENUE FROM SFX_BILLING.INVOICE_HDR i
       | JOIN selected_subscriptions s ON s.SUBSCRIPTION_ID = i.SUBSCRIPTION_ID
       | WHERE INVOICE_DT >= ADD_MONTHS(CURRENT_DATE - CAST(EXTRACT(DAY FROM CURRENT_DATE) AS INTEGER) + 1, -11)
       | AND INVOICE_DT < ADD_MONTHS(CURRENT_DATE - CAST(EXTRACT(DAY FROM CURRENT_DATE) AS INTEGER) + 1, 1)
       | GROUP BY 1, 2
       |), cash AS (
       | SEL p.CUSTOMER_ID, EXTRACT(YEAR FROM p.PAYMENT_DT) * 100 + EXTRACT(MONTH FROM p.PAYMENT_DT) AS PERIOD_ID,
       | SUM(p.AMOUNT) AS COLLECTED FROM SFX_BILLING.PAYMENT p
       | JOIN SFX_BILLING.INVOICE_HDR i ON i.INVOICE_ID = p.INVOICE_ID
       | JOIN selected_subscriptions s ON s.SUBSCRIPTION_ID = i.SUBSCRIPTION_ID
       | WHERE PAYMENT_DT >= ADD_MONTHS(CURRENT_DATE - CAST(EXTRACT(DAY FROM CURRENT_DATE) AS INTEGER) + 1, -11)
       | AND PAYMENT_DT < ADD_MONTHS(CURRENT_DATE - CAST(EXTRACT(DAY FROM CURRENT_DATE) AS INTEGER) + 1, 1)
       | GROUP BY 1, 2
       |)
       |SEL CAST(CAST(m.MONTH_START AS FORMAT 'YYYY-MM') AS CHAR(7)) AS MONTH_LABEL, a.REGION_CD, a.PLAN_NAME,
       | ZEROIFNULL(SUM(b.REVENUE)) AS BILLED_REVENUE, ZEROIFNULL(SUM(p.COLLECTED)) AS COLLECTED_CASH,
       | SUM(CASE WHEN a.STATUS_CD = 'ACTIVE' AND a.CREATED_DT < ADD_MONTHS(m.MONTH_START, 1)
       | THEN 1 ELSE 0 END) AS ACTIVE_ACCOUNTS
       |FROM months m CROSS JOIN accounts a
       |LEFT JOIN billed b ON b.CUSTOMER_ID = a.CUSTOMER_ID
       | AND b.PERIOD_ID = EXTRACT(YEAR FROM m.MONTH_START) * 100 + EXTRACT(MONTH FROM m.MONTH_START)
       |LEFT JOIN cash p ON p.CUSTOMER_ID = a.CUSTOMER_ID
       | AND p.PERIOD_ID = EXTRACT(YEAR FROM m.MONTH_START) * 100 + EXTRACT(MONTH FROM m.MONTH_START)
       |GROUP BY 1, 2, 3 ORDER BY 1, 2, 3""".stripMargin

class TeradataFinanceRollupRepository(connect: () => Connection)(using ec: ExecutionContext)
    extends FinanceRollupRepository:
  def this(settings: FinanceSettings)(using ExecutionContext) =
    this(() => DriverManager.getConnection(settings.url, settings.user, settings.password))

  override def rollups(status: String, plan: String): Future[List[FinanceRollup]] = Future {
    blocking {
      val connection = connect()
      try
        val statement = connection.prepareStatement(TeradataFinanceRollupRepository.Sql)
        try
          statement.setString(1, status)
          statement.setString(2, plan)
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

class CachedFinanceRollups(delegate: FinanceRollupRepository, ttlNanos: Long = 900000000000L,
                          now: () => Long = () => System.nanoTime())(using ec: ExecutionContext)
    extends FinanceRollupRepository:
  private var cache = Map.empty[(String, String), (Long, List[FinanceRollup])]
  override def rollups(status: String, plan: String): Future[List[FinanceRollup]] = synchronized {
    val key = (status, plan)
    cache.get(key).filter(entry => now() - entry._1 < ttlNanos) match
      case Some((_, rows)) => Future.successful(rows)
      case None => delegate.rollups(status, plan).map { rows =>
        synchronized { cache = cache.filter(entry => now() - entry._2._1 < ttlNanos) + (key -> (now(), rows)) }
        rows
      }
  }
