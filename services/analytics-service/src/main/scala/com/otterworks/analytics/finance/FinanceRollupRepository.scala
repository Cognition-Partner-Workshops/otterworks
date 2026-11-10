package com.otterworks.analytics.finance

import com.typesafe.config.Config
import java.sql.{Connection, DriverManager}
import scala.concurrent.{ExecutionContext, Future, blocking}
import scala.collection.mutable.ListBuffer

case class FinanceRollup(month: String, region: String, plan: String,
                         billedRevenue: BigDecimal, collectedCash: BigDecimal, activeAccounts: Long)

trait FinanceRollupRepository:
  def rollups(region: String, plan: String): Future[List[FinanceRollup]]

case class FinanceSettings(enabled: Boolean, regions: List[String], featuredPlan: String,
                           url: String, user: String, password: String)

object FinanceSettings:
  def load(config: Config): FinanceSettings =
    import scala.jdk.CollectionConverters.*
    val c = config.getConfig("finance.warehouse")
    FinanceSettings(c.getBoolean("enabled"), c.getStringList("regions").asScala.toList,
      c.getString("featured-plan"), c.getString("url"), c.getString("user"), c.getString("password"))

object TeradataFinanceRollupRepository:
  private val offsets = (0 until 12).map(n => s"SEL $n AS N").mkString(" UNION ALL ")
  val Sql: String =
    s"""WITH months AS (
       | SEL TOP 12 ADD_MONTHS(CURRENT_DATE - EXTRACT(DAY FROM CURRENT_DATE) + 1, -N) AS MONTH_START
       | FROM ($offsets) offsets
       |), accounts AS (
       | SEL a.ACCOUNT_ID, a.PLAN_NAME, a.STATUS_CD, a.OPENED_DT, c.REGION_CODE
       | FROM FIN_DW.ACCOUNT a JOIN FIN_DW.CUSTOMER c ON c.CUSTOMER_ID = a.CUSTOMER_ID
       | WHERE c.REGION_CODE = ? AND a.PLAN_NAME = ?
       |), billed AS (
       | SEL ACCOUNT_ID, EXTRACT(YEAR FROM INVOICE_DT) * 100 + EXTRACT(MONTH FROM INVOICE_DT) AS PERIOD_ID,
       | SUM(AMOUNT_DUE - TAX_AMT) AS REVENUE FROM FIN_DW.INVOICE
       | WHERE INVOICE_DT >= ADD_MONTHS(CURRENT_DATE - EXTRACT(DAY FROM CURRENT_DATE) + 1, -11)
       | AND INVOICE_DT < ADD_MONTHS(CURRENT_DATE - EXTRACT(DAY FROM CURRENT_DATE) + 1, 1)
       | GROUP BY 1, 2
       |), cash AS (
       | SEL ACCOUNT_ID, EXTRACT(YEAR FROM PAYMENT_DT) * 100 + EXTRACT(MONTH FROM PAYMENT_DT) AS PERIOD_ID,
       | SUM(AMOUNT) AS COLLECTED FROM FIN_DW.PAYMENT
       | WHERE PAYMENT_DT >= ADD_MONTHS(CURRENT_DATE - EXTRACT(DAY FROM CURRENT_DATE) + 1, -11)
       | AND PAYMENT_DT < ADD_MONTHS(CURRENT_DATE - EXTRACT(DAY FROM CURRENT_DATE) + 1, 1)
       | GROUP BY 1, 2
       |)
       |SEL (m.MONTH_START (FORMAT 'YYYY-MM') (CHAR(7))) AS MONTH_LABEL, a.REGION_CODE, a.PLAN_NAME,
       | ZEROIFNULL(SUM(b.REVENUE)) AS BILLED_REVENUE, ZEROIFNULL(SUM(p.COLLECTED)) AS COLLECTED_CASH,
       | SUM(CASE WHEN a.STATUS_CD = 'A' AND a.OPENED_DT < ADD_MONTHS(m.MONTH_START, 1)
       | THEN 1 ELSE 0 END) AS ACTIVE_ACCOUNTS
       |FROM months m CROSS JOIN accounts a
       |LEFT JOIN billed b ON b.ACCOUNT_ID = a.ACCOUNT_ID
       | AND b.PERIOD_ID = EXTRACT(YEAR FROM m.MONTH_START) * 100 + EXTRACT(MONTH FROM m.MONTH_START)
       |LEFT JOIN cash p ON p.ACCOUNT_ID = a.ACCOUNT_ID
       | AND p.PERIOD_ID = EXTRACT(YEAR FROM m.MONTH_START) * 100 + EXTRACT(MONTH FROM m.MONTH_START)
       |GROUP BY 1, 2, 3 ORDER BY 1, 2, 3""".stripMargin

class TeradataFinanceRollupRepository(connect: () => Connection)(using ec: ExecutionContext)
    extends FinanceRollupRepository:
  def this(settings: FinanceSettings)(using ExecutionContext) =
    this(() => DriverManager.getConnection(settings.url, settings.user, settings.password))

  override def rollups(region: String, plan: String): Future[List[FinanceRollup]] = Future {
    blocking {
      val connection = connect()
      try
        val statement = connection.prepareStatement(TeradataFinanceRollupRepository.Sql)
        try
          statement.setString(1, region)
          statement.setString(2, plan)
          val rs = statement.executeQuery()
          try
            val rows = ListBuffer.empty[FinanceRollup]
            while rs.next() do
              rows += FinanceRollup(rs.getString("MONTH_LABEL"), rs.getString("REGION_CODE"),
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
  override def rollups(region: String, plan: String): Future[List[FinanceRollup]] = synchronized {
    val key = (region, plan)
    cache.get(key).filter(entry => now() - entry._1 < ttlNanos) match
      case Some((_, rows)) => Future.successful(rows)
      case None => delegate.rollups(region, plan).map { rows =>
        synchronized { cache = cache.filter(entry => now() - entry._2._1 < ttlNanos) + (key -> (now(), rows)) }
        rows
      }
  }
