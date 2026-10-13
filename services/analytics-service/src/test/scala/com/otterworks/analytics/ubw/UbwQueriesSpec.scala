package com.otterworks.analytics.ubw

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers

class UbwQueriesSpec extends AnyFlatSpec with Matchers:

  "UbwBackend" should "default to sqlserver and accept snowflake" in {
    UbwBackend.parse(null) shouldBe UbwBackend.SqlServer
    UbwBackend.parse(" Snowflake ") shouldBe UbwBackend.Snowflake
    an[IllegalArgumentException] should be thrownBy UbwBackend.parse("oracle")
  }

  "UbwQueries" should "read the legacy tables on sqlserver" in {
    UbwQueries.source(UbwBackend.SqlServer, UbwQueries.usageByKind(UbwBackend.SqlServer)) shouldBe "fact.fact_usage_events"
    UbwQueries.source(UbwBackend.SqlServer, UbwQueries.tenantUsage(UbwBackend.SqlServer)) shouldBe "mart.mart_tenant_usage_daily"
  }

  it should "read the dbt model and the REPORTS view on snowflake" in {
    UbwQueries.source(UbwBackend.Snowflake, UbwQueries.usageByKind(UbwBackend.Snowflake)) shouldBe "MARTS.ROLLUP_USAGE_EVENTS"
    UbwQueries.source(UbwBackend.Snowflake, UbwQueries.tenantUsage(UbwBackend.Snowflake)) shouldBe "REPORTS.RPT_TENANT_USAGE_DAILY"
  }

  "UbwConnections.prefix" should "follow the run token naming" in {
    UbwConnections.prefix("sfm-20261013-lv") shouldBe "OW_UBW_SFM_20261013_LV"
    an[IllegalStateException] should be thrownBy UbwConnections.prefix("prod")
  }
