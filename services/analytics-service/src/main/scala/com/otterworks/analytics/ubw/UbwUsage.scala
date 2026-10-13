package com.otterworks.analytics.ubw

import akka.http.scaladsl.model.{ContentTypes, HttpEntity, StatusCodes}
import akka.http.scaladsl.server.Directives.*
import akka.http.scaladsl.server.Route
import io.circe.Json
import io.circe.syntax.*

import java.security.KeyFactory
import java.security.spec.PKCS8EncodedKeySpec
import java.sql.{Connection, DriverManager}
import java.time.LocalDate
import java.util.{Base64, Locale, Properties}
import scala.concurrent.{ExecutionContext, Future}
import scala.util.Using

/** Which Usage & Billing Warehouse the usage API reads (UBW_BACKEND=sqlserver|snowflake). */
enum UbwBackend:
  case SqlServer, Snowflake
  def label: String = if this == Snowflake then "snowflake" else "sqlserver"

object UbwBackend:
  def parse(value: String): UbwBackend =
    Option(value).map(_.trim.toLowerCase(Locale.ROOT)).getOrElse("") match
      case "" | "sqlserver" => SqlServer
      case "snowflake"      => Snowflake
      case other            => throw IllegalArgumentException(s"Unknown UBW_BACKEND: $other")

/**
 * The two warehouse reads analytics-service makes for the usage API (consumers.yaml): usage units
 * per tenant and event kind from the usage-event fact, and the tenant usage mart. On SQL Server they
 * read fact.fact_usage_events and mart.mart_tenant_usage_daily; on Snowflake they read
 * MARTS.ROLLUP_USAGE_EVENTS (the dbt model that replaces the fact) and the
 * REPORTS.RPT_TENANT_USAGE_DAILY view.
 */
object UbwQueries:
  def usageByKind(backend: UbwBackend): String =
    val source = if backend == UbwBackend.Snowflake then "MARTS.ROLLUP_USAGE_EVENTS" else "fact.fact_usage_events"
    s"SELECT business_date, tenant_id, event_kind, SUM(units) AS units FROM $source " +
      "WHERE business_date = ? GROUP BY business_date, tenant_id, event_kind ORDER BY tenant_id, event_kind"

  def tenantUsage(backend: UbwBackend): String =
    val source = if backend == UbwBackend.Snowflake then "REPORTS.RPT_TENANT_USAGE_DAILY" else "mart.mart_tenant_usage_daily"
    s"SELECT business_date, tenant_id, tenant_name, plan_tier, api_units, compute_units, active_users FROM $source " +
      "WHERE business_date = ? ORDER BY tenant_name"

  def source(backend: UbwBackend, query: String): String =
    query.split("\\s+").dropWhile(_.toUpperCase(Locale.ROOT) != "FROM").drop(1).headOption.getOrElse("")

final class UbwConnections(env: String => Option[String] = sys.env.get):
  val backend: UbwBackend = UbwBackend.parse(env("UBW_BACKEND").orNull)

  def open(): Connection = backend match
    case UbwBackend.SqlServer =>
      val url = env("UBW_SQL_URL").getOrElse(
        s"jdbc:sqlserver://${env("UBW_SQL_HOST").getOrElse("localhost")}:${env("UBW_SQL_PORT").getOrElse("1433")};" +
          s"databaseName=${env("UBW_SQL_DATABASE").getOrElse("OtterWorksUBW")};encrypt=false")
      DriverManager.getConnection(url, env("UBW_SQL_USER").getOrElse(""), env("UBW_SQL_PASSWORD").getOrElse(""))
    case UbwBackend.Snowflake =>
      val prefix = UbwConnections.prefix(env("UBW_RUN").getOrElse(""))
      val host = env("SNOWFLAKE_HOST").getOrElse(s"${env("SNOWFLAKE_ACCOUNT").getOrElse("")}.snowflakecomputing.com")
      val role = env("UBW_SNOWFLAKE_ROLE").getOrElse(s"${prefix}_ENGINEER")
      val properties = Properties()
      properties.put("user", env("UBW_SNOWFLAKE_USER").orElse(env("UBW_DBT_USER")).getOrElse(s"${prefix}_DBT"))
      properties.put("privateKey", UbwConnections.privateKey(
        env("SNOWFLAKE_PRIVATE_KEY").orElse(env("UBW_DBT_PRIVATE_KEY")).getOrElse("")))
      properties.put("JDBC_QUERY_RESULT_FORMAT", "JSON")
      DriverManager.getConnection(
        s"jdbc:snowflake://$host/?db=$prefix&warehouse=${prefix}_WH&role=$role", properties)

object UbwConnections:
  private val Run = "^sfm-\\d{8}-[a-z0-9]{2,8}$".r

  def prefix(run: String): String =
    if Run.matches(run) then "OW_UBW_" + run.toUpperCase(Locale.ROOT).replace('-', '_')
    else throw IllegalStateException(s"UBW_RUN $run does not look like sfm-<yyyymmdd>-<suffix>")

  def privateKey(pem: String): java.security.PrivateKey =
    val body = pem.replaceAll("-----(BEGIN|END) PRIVATE KEY-----", "").replaceAll("\\s", "")
    KeyFactory.getInstance("RSA").generatePrivate(PKCS8EncodedKeySpec(Base64.getDecoder.decode(body)))

/** GET /api/v1/analytics/ubw/usage and /api/v1/analytics/ubw/tenant-usage?businessDate=yyyy-MM-dd */
class UbwRoutes(connections: UbwConnections)(using ec: ExecutionContext):

  private def query(sql: String, businessDate: LocalDate): Future[Json] = Future {
    Using.resource(connections.open()) { connection =>
      Using.resource(connection.prepareStatement(sql)) { statement =>
        statement.setDate(1, java.sql.Date.valueOf(businessDate))
        Using.resource(statement.executeQuery()) { results =>
          val meta = results.getMetaData
          val names = (1 to meta.getColumnCount).map(i => meta.getColumnLabel(i).toLowerCase(Locale.ROOT))
          val rows = Iterator.continually(results).takeWhile(_.next()).map { row =>
            Json.obj(names.zipWithIndex.map { (name, index) =>
              name -> Option(row.getObject(index + 1)).map(_.toString.asJson).getOrElse(Json.Null)
            }*)
          }.toVector
          Json.obj(
            "backend" -> connections.backend.label.asJson,
            "source" -> UbwQueries.source(connections.backend, sql).asJson,
            "businessDate" -> businessDate.toString.asJson,
            "rowCount" -> rows.size.asJson,
            "rows" -> Json.arr(rows*),
          )
        }
      }
    }
  }

  private def respond(sql: String, date: String): Route =
    scala.util.Try(LocalDate.parse(date)).toOption match
      case None => complete(StatusCodes.BadRequest, "businessDate must be yyyy-MM-dd")
      case Some(businessDate) =>
        onSuccess(query(sql, businessDate)) { json =>
          complete(HttpEntity(ContentTypes.`application/json`, json.noSpaces))
        }

  val routes: Route = pathPrefix("api" / "v1" / "analytics" / "ubw") {
    get {
      parameters("businessDate") { date =>
        concat(
          path("usage")(respond(UbwQueries.usageByKind(connections.backend), date)),
          path("tenant-usage")(respond(UbwQueries.tenantUsage(connections.backend), date)),
        )
      }
    }
  }
