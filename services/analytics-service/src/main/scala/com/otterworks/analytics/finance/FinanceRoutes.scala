package com.otterworks.analytics.finance

import akka.http.scaladsl.model.{ContentTypes, HttpEntity, StatusCodes}
import akka.http.scaladsl.server.Directives.*
import akka.http.scaladsl.server.Route
import spray.json.DefaultJsonProtocol.{*, given}
import spray.json.*
import scala.util.{Failure, Success}

class FinanceRoutes(repository: FinanceRollupRepository, settings: FinanceSettings):
  private given spray.json.RootJsonFormat[FinanceRollup] = jsonFormat6(FinanceRollup.apply)

  val routes: Route =
    if !settings.enabled then reject
    else path("api" / "v1" / "analytics" / "finance" / "rollups") {
      get {
        parameters("region".withDefault(settings.regions.head), "plan".withDefault(settings.featuredPlan)) {
          (region, plan) =>
            if region.isEmpty || plan.isEmpty || region.length > 16 || plan.length > 40 then
              complete(StatusCodes.BadRequest, "invalid region or plan")
            else
              onComplete(repository.rollups(region, plan)) {
                case Success(rows) =>
                  complete(HttpEntity(ContentTypes.`application/json`, rows.toJson.compactPrint))
                case Failure(_) => complete(StatusCodes.ServiceUnavailable, "finance warehouse unavailable")
              }
        }
      }
    }
