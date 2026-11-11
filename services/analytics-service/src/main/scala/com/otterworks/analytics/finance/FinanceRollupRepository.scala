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
                           account: String, user: String, role: String, privateKey: String)

object FinanceSettings:
  def load(config: Config): FinanceSettings =
    import scala.jdk.CollectionConverters.*
    val c = config.getConfig("finance.warehouse")
    FinanceSettings(c.getBoolean("enabled"), c.getStringList("statuses").asScala.toList,
      c.getString("featured-plan"), c.getString("account"), c.getString("user"), c.getString("role"), c.getString("private-key"))

object FinanceRollupSql:
  val SubscriptionFilter = "UPPER(RTRIM(s.STATUS_CD)) = UPPER(RTRIM(?)) AND UPPER(RTRIM(s.PLAN_CODE)) = UPPER(RTRIM(?))"
  val PlanJoin = "UPPER(RTRIM(p.PLAN_CODE)) = UPPER(RTRIM(s.PLAN_CODE))"
  val ActiveAccount = "UPPER(RTRIM(a.STATUS_CD)) = 'ACTIVE'"

object SnowflakeFinanceRollupRepository:
  private val offsets = (0 until 12).map(n => s"SELECT $n AS N").mkString(" UNION ALL ")
  val Sql: String =
    s"""WITH months AS (
       | SELECT ADD_MONTHS(DATE_TRUNC('MONTH', CURRENT_DATE()), -N) AS MONTH_START
       | FROM ($offsets) offsets
       |), selected_subscriptions AS (
       | SELECT DISTINCT s.SUBSCRIPTION_ID, s.CUSTOMER_ID, p.PLAN_NAME
       | FROM SFX_D1110_AFTER.CORE_BILLING.STG_BILLING__SUBSCRIPTION s JOIN SFX_D1110_AFTER.CORE_BILLING.STG_BILLING__PLAN_CATALOG p ON ${FinanceRollupSql.PlanJoin}
       | WHERE ${FinanceRollupSql.SubscriptionFilter}
       |), accounts AS (
       | SELECT DISTINCT c.CUSTOMER_ID, c.REGION_CD, c.STATUS_CD, c.CREATED_DT, s.PLAN_NAME
       | FROM SFX_D1110_AFTER.COMPAT.CUSTOMER_ACCOUNT c JOIN selected_subscriptions s ON s.CUSTOMER_ID = c.CUSTOMER_ID
       |), billed AS (
       | SELECT i.CUSTOMER_ID, EXTRACT(YEAR FROM i.INVOICE_DT) * 100 + EXTRACT(MONTH FROM i.INVOICE_DT) AS PERIOD_ID,
       | SUM(i.SUBTOTAL_AMOUNT) AS REVENUE FROM SFX_D1110_AFTER.COMPAT.INVOICE_HDR i
       | JOIN selected_subscriptions s ON s.SUBSCRIPTION_ID = i.SUBSCRIPTION_ID
       | WHERE INVOICE_DT >= ADD_MONTHS(DATE_TRUNC('MONTH', CURRENT_DATE()), -11)
       | AND INVOICE_DT < ADD_MONTHS(DATE_TRUNC('MONTH', CURRENT_DATE()), 1)
       | GROUP BY 1, 2
       |), cash AS (
       | SELECT p.CUSTOMER_ID, EXTRACT(YEAR FROM p.PAYMENT_DT) * 100 + EXTRACT(MONTH FROM p.PAYMENT_DT) AS PERIOD_ID,
       | SUM(p.AMOUNT) AS COLLECTED FROM SFX_D1110_AFTER.COMPAT.PAYMENT p
       | JOIN SFX_D1110_AFTER.COMPAT.INVOICE_HDR i ON i.INVOICE_ID = p.INVOICE_ID
       | JOIN selected_subscriptions s ON s.SUBSCRIPTION_ID = i.SUBSCRIPTION_ID
       | WHERE PAYMENT_DT >= ADD_MONTHS(DATE_TRUNC('MONTH', CURRENT_DATE()), -11)
       | AND PAYMENT_DT < ADD_MONTHS(DATE_TRUNC('MONTH', CURRENT_DATE()), 1)
       | GROUP BY 1, 2
       |)
       |SELECT TO_CHAR(m.MONTH_START, 'YYYY-MM') AS MONTH_LABEL, a.REGION_CD, a.PLAN_NAME,
       | COALESCE(SUM(b.REVENUE), 0) AS BILLED_REVENUE, COALESCE(SUM(p.COLLECTED), 0) AS COLLECTED_CASH,
       | SUM(CASE WHEN ${FinanceRollupSql.ActiveAccount} AND a.CREATED_DT < ADD_MONTHS(m.MONTH_START, 1)
       | THEN 1 ELSE 0 END) AS ACTIVE_ACCOUNTS
       |FROM months m CROSS JOIN accounts a
       |LEFT JOIN billed b ON b.CUSTOMER_ID = a.CUSTOMER_ID
       | AND b.PERIOD_ID = EXTRACT(YEAR FROM m.MONTH_START) * 100 + EXTRACT(MONTH FROM m.MONTH_START)
       |LEFT JOIN cash p ON p.CUSTOMER_ID = a.CUSTOMER_ID
       | AND p.PERIOD_ID = EXTRACT(YEAR FROM m.MONTH_START) * 100 + EXTRACT(MONTH FROM m.MONTH_START)
       |GROUP BY 1, 2, 3 ORDER BY 1, 2, 3""".stripMargin


  val RetainedQueryIds = 32
  val QueryTag = """{"run":"sfx-d1110","act":"consumers","consumer":"analytics-service"}"""
  def connect(settings: FinanceSettings): Connection =
    val pem = settings.privateKey.replace("-----BEGIN PRIVATE KEY-----", "")
      .replace("-----END PRIVATE KEY-----", "").replaceAll("\\s", "")
    val key = java.security.KeyFactory.getInstance("RSA").generatePrivate(
      new java.security.spec.PKCS8EncodedKeySpec(java.util.Base64.getDecoder.decode(pem)))
    val properties = new java.util.Properties()
    properties.setProperty("user", settings.user)
    properties.setProperty("role", settings.role)
    properties.setProperty("warehouse", "SFX_D1110_PARITY_WH")
    properties.setProperty("db", "SFX_D1110_AFTER")
    properties.setProperty("schema", "COMPAT")
    properties.setProperty("authenticator", "SNOWFLAKE_JWT")
    properties.put("privateKey", key)
    properties.setProperty("QUERY_TAG", QueryTag)
    properties.setProperty("TIMEZONE", "UTC")
    properties.setProperty("JDBC_QUERY_RESULT_FORMAT", "JSON")
    DriverManager.getConnection(s"jdbc:snowflake://${settings.account}.snowflakecomputing.com", properties)

class SnowflakeFinanceRollupRepository(connect: () => Connection,
                                       retainedQueryIds: Int = SnowflakeFinanceRollupRepository.RetainedQueryIds)
                                      (using ec: ExecutionContext)
    extends FinanceRollupRepository:
  require(retainedQueryIds > 0, "retainedQueryIds must be positive")
  private val recentQueryIds = scala.collection.mutable.ArrayDeque.empty[String]
  def this(settings: FinanceSettings)(using ExecutionContext) =
    this(() => SnowflakeFinanceRollupRepository.connect(settings))

  /** The most recent Snowflake query IDs, oldest first. */
  def queryIds: List[String] = recentQueryIds.synchronized(recentQueryIds.toList)

  private def rememberQueryId(id: String): Unit = recentQueryIds.synchronized {
    recentQueryIds.append(id)
    while recentQueryIds.size > retainedQueryIds do recentQueryIds.removeHead()
  }

  override def rollups(status: String, plan: String): Future[List[FinanceRollup]] = Future {
    blocking {
      val connection = connect()
      try
        val statement = connection.prepareStatement(SnowflakeFinanceRollupRepository.Sql)
        try
          statement.setString(1, status)
          statement.setString(2, plan)
          val rs = statement.executeQuery()
          if rs.isWrapperFor(classOf[net.snowflake.client.jdbc.SnowflakeResultSet]) then
            rememberQueryId(rs.unwrap(classOf[net.snowflake.client.jdbc.SnowflakeResultSet]).getQueryID)
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
