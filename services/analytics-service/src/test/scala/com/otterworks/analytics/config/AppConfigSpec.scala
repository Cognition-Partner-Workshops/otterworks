package com.otterworks.analytics.config

import com.typesafe.config.{ConfigException, ConfigFactory, ConfigResolveOptions}
import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers

import java.io.File

class AppConfigSpec extends AnyFlatSpec with Matchers:

  private val shippedConf = new File("src/main/resources/application.conf")

  private def shippedWith(env: Map[String, String]) =
    val overrides = env.map { case (k, v) => s"""$k = "$v"""" }.mkString("\n")
    ConfigFactory
      .parseString(overrides)
      .withFallback(ConfigFactory.parseFile(shippedConf))
      .resolve(ConfigResolveOptions.defaults().setUseSystemEnvironment(false))

  "the shipped application.conf" should "carry no default postgres password" in {
    shippedWith(Map.empty).hasPath("analytics.postgres.password") shouldBe false
  }

  it should "refuse to load with the postgres backend and no password env var" in {
    val ex = intercept[ConfigException.Missing] {
      AppConfig.fromConfig(shippedWith(Map.empty))
    }
    ex.getMessage should include("analytics.postgres.password")
  }

  it should "take the password from POSTGRES_PASSWORD" in {
    AppConfig.fromConfig(shippedWith(Map("POSTGRES_PASSWORD" -> "from-postgres-env")))
      .postgres.password shouldBe "from-postgres-env"
  }

  it should "prefer DATABASE_PASSWORD over POSTGRES_PASSWORD" in {
    val cfg = shippedWith(Map("POSTGRES_PASSWORD" -> "pg", "DATABASE_PASSWORD" -> "db"))
    AppConfig.fromConfig(cfg).postgres.password shouldBe "db"
  }

  it should "still load with the in-memory backend and no password" in {
    val cfg = shippedWith(Map("ANALYTICS_REPOSITORY_BACKEND" -> "in-memory"))
    AppConfig.fromConfig(cfg).postgres.password shouldBe ""
  }
