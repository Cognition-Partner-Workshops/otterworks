package com.otterworks.analytics.finance

import akka.http.scaladsl.model.StatusCodes
import akka.http.scaladsl.server.Route
import akka.http.scaladsl.testkit.ScalatestRouteTest
import com.typesafe.config.ConfigFactory
import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers
import java.lang.reflect.{InvocationHandler, Method, Proxy}
import java.sql.{Connection, PreparedStatement, ResultSet, SQLException}
import scala.concurrent.{Await, Future}
import scala.concurrent.duration.*
import spray.json.*

class FinanceRollupSpec extends AnyFlatSpec with Matchers with ScalatestRouteTest:
  private val settings = FinanceSettings.load(ConfigFactory.parseResources(
    "com/otterworks/analytics/finance/snowflake.conf").resolve())
  private val row = FinanceRollup("2026-01", "California", "Workspace Team - Monthly", BigDecimal("18000.50"),
    BigDecimal("15000.25"), 14)

  private def proxy[A](kind: Class[A])(f: (String, Array[Object]) => Object): A =
    Proxy.newProxyInstance(kind.getClassLoader, Array(kind), new InvocationHandler:
      override def invoke(target: Object, method: Method, args: Array[Object]): Object =
        f(method.getName, Option(args).getOrElse(Array.empty[Object]))
    ).asInstanceOf[A]

  "Finance JDBC" should "bind filters, map rows and close resources" in {
    var bound = Map.empty[Int, String]
    var closed = Set.empty[String]
    var next = true
    val rs = proxy(classOf[ResultSet]) { (method, args) =>
      method match
        case "next" => val value = next; next = false; Boolean.box(value)
        case "getString" => Map("MONTH_LABEL" -> row.month, "REGION_CD" -> row.region,
          "PLAN_NAME" -> row.plan)(args(0).toString)
        case "getBigDecimal" => (if args(0) == "BILLED_REVENUE" then row.billedRevenue
          else row.collectedCash).bigDecimal
        case "getLong" => Long.box(row.activeAccounts)
        case "isWrapperFor" => Boolean.box(false)
        case "close" => closed += "result"; null
        case _ => throw new UnsupportedOperationException(method)
    }
    val statement = proxy(classOf[PreparedStatement]) { (method, args) =>
      method match
        case "setString" => bound += args(0).asInstanceOf[Integer].intValue -> args(1).toString; null
        case "executeQuery" => rs
        case "close" => closed += "statement"; null
        case _ => throw new UnsupportedOperationException(method)
    }
    val connection = proxy(classOf[Connection]) { (method, args) =>
      method match
        case "prepareStatement" => args(0) shouldBe SnowflakeFinanceRollupRepository.Sql; statement
        case "close" => closed += "connection"; null
        case _ => throw new UnsupportedOperationException(method)
    }
    val repo = new SnowflakeFinanceRollupRepository(() => connection)
    Await.result(repo.rollups(settings.statuses.head, settings.featuredPlan), 3.seconds) shouldBe List(row)
    bound shouldBe Map(1 -> settings.statuses.head, 2 -> settings.featuredPlan)
    closed shouldBe Set("connection", "statement", "result")
    Await.result(repo.rollups("Pending", "PRO"), 3.seconds) shouldBe empty
  }

  it should "return connection failures through the future" in {
    val repo = new SnowflakeFinanceRollupRepository(() => throw new SQLException("unavailable"))
    intercept[SQLException](Await.result(repo.rollups(settings.statuses.head, settings.featuredPlan), 3.seconds))
  }

  "Finance route" should "serve defaults and supplied filters" in {
    var filters = List.empty[(String, String)]
    val repo = new FinanceRollupRepository:
      def rollups(status: String, plan: String) =
        filters = filters :+ (status, plan)
        Future.successful(List(row))
    val routes = new FinanceRoutes(repo, settings).routes
    Get("/api/v1/analytics/finance/rollups") ~> routes ~> check {
      status shouldBe StatusCodes.OK
      responseAs[String].parseJson.asInstanceOf[JsArray].elements.size shouldBe 1
    }
    Get("/api/v1/analytics/finance/rollups?status=Pending&plan=PRO") ~> routes ~> check {
      status shouldBe StatusCodes.OK
    }
    filters shouldBe List((settings.statuses.head, settings.featuredPlan), ("Pending", "PRO"))
  }

  it should "serve empty results and reject invalid filters" in {
    val repo = new FinanceRollupRepository:
      def rollups(status: String, plan: String) = Future.successful(Nil)
    val routes = new FinanceRoutes(repo, settings).routes
    Get("/api/v1/analytics/finance/rollups") ~> routes ~> check {
      responseAs[String].parseJson shouldBe JsArray()
    }
    Get("/api/v1/analytics/finance/rollups?status=") ~> routes ~> check {
      status shouldBe StatusCodes.BadRequest
    }
    Get("/api/v1/analytics/finance/rollups") ~>
      Route.seal(new FinanceRoutes(repo, settings.copy(enabled = false)).routes) ~> check {
        status shouldBe StatusCodes.NotFound
      }
  }

  it should "sanitize warehouse failures" in {
    val repo = new FinanceRollupRepository:
      def rollups(status: String, plan: String) = Future.failed(new SQLException("private details"))
    Get("/api/v1/analytics/finance/rollups") ~> new FinanceRoutes(repo, settings).routes ~> check {
      status shouldBe StatusCodes.ServiceUnavailable
      responseAs[String] shouldBe "finance warehouse unavailable"
    }
  }

  "Finance cache" should "reuse successful rows until expiry and isolate filters" in {
    var calls = 0
    var clock = 0L
    val delegate = new FinanceRollupRepository:
      def rollups(status: String, plan: String) =
        calls += 1
        Future.successful(List(row))
    val cache = new CachedFinanceRollups(delegate, 100L, () => clock)
    def load(status: String) = Await.result(cache.rollups(status, settings.featuredPlan), 3.seconds)
    load("Active")
    load("Active")
    calls shouldBe 1
    load("Pending")
    calls shouldBe 2
    clock = 101L
    load("Active")
    calls shouldBe 3
  }
