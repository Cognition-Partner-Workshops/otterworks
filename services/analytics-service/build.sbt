val scala3Version = "3.4.0"
val jacksonVersion = "2.18.11"
val nettyVersion = "4.1.137.Final"

lazy val root = project
  .in(file("."))
  .settings(
    name := "analytics-service",
    version := "0.1.0",
    scalaVersion := scala3Version,
    // The HTTP server is the default entrypoint (`java -jar`). The batch job
    // (com.otterworks.analytics.batch.UsageRollupJob) is a second main class run
    // explicitly via `java -cp app.jar ...` (see the analytics-service CronJob).
    Compile / mainClass := Some("com.otterworks.analytics.Main"),
    assembly / mainClass := Some("com.otterworks.analytics.Main"),
    libraryDependencies ++= Seq(
      // Akka HTTP
      "com.typesafe.akka" %% "akka-http" % "10.5.3" cross CrossVersion.for3Use2_13,
      "com.typesafe.akka" %% "akka-actor-typed" % "2.8.8" cross CrossVersion.for3Use2_13,
      "com.typesafe.akka" %% "akka-stream" % "2.8.8" cross CrossVersion.for3Use2_13,
      "com.typesafe.akka" %% "akka-http-spray-json" % "10.5.3" cross CrossVersion.for3Use2_13,

      // JSON
      "io.circe" %% "circe-core" % "0.14.6",
      "io.circe" %% "circe-generic" % "0.14.6",
      "io.circe" %% "circe-parser" % "0.14.6",

      // Database - Slick for PostgreSQL
      "com.typesafe.slick" %% "slick" % "3.5.2" cross CrossVersion.for3Use2_13,
      "com.typesafe.slick" %% "slick-hikaricp" % "3.5.2" cross CrossVersion.for3Use2_13,
      "org.postgresql" % "postgresql" % "42.7.12",

      // Schema migrations (Flyway bundles PostgreSQL support in the 9.x line)
      "org.flywaydb" % "flyway-core" % "9.22.3",

      // AWS SDK
      "software.amazon.awssdk" % "s3" % "2.25.6",
      "software.amazon.awssdk" % "sqs" % "2.25.6",

      // Configuration
      "com.typesafe" % "config" % "1.4.3",

      // Logging
      "ch.qos.logback" % "logback-classic" % "1.5.34",
      "net.logstash.logback" % "logstash-logback-encoder" % "7.4",
      "org.slf4j" % "slf4j-api" % "2.0.12",

      // Metrics
      "io.prometheus" % "simpleclient" % "0.16.0",
      "io.prometheus" % "simpleclient_common" % "0.16.0",
      "io.prometheus" % "simpleclient_hotspot" % "0.16.0",

      // Testing
      "org.scalatest" %% "scalatest" % "3.2.18" % Test,
      "com.typesafe.akka" %% "akka-http-testkit" % "10.5.3" % Test cross CrossVersion.for3Use2_13,
      "com.typesafe.akka" %% "akka-stream-testkit" % "2.8.8" % Test cross CrossVersion.for3Use2_13,
      "com.typesafe.akka" %% "akka-actor-testkit-typed" % "2.8.8" % Test cross CrossVersion.for3Use2_13,

      // Integration testing against a real PostgreSQL (skipped when Docker is unavailable)
      "com.dimafeng" %% "testcontainers-scala-scalatest" % "0.41.4" % Test,
      "com.dimafeng" %% "testcontainers-scala-postgresql" % "0.41.4" % Test,
    ),
    // Transitive pins: no parent release in our lines pulls fixed versions.
    // Jackson (logstash-logback-encoder, testcontainers) -> 2.18.11;
    // Netty (AWS SDK netty-nio-client) -> 4.1.137.Final; jawn-parser (circe-parser) -> 1.7.0;
    // commons-compress (testcontainers, Test only) -> 1.26.0, and the commons-lang3 it pulls -> 3.18.0.
    dependencyOverrides ++= Seq(
      "com.fasterxml.jackson.core" % "jackson-core" % jacksonVersion,
      "com.fasterxml.jackson.core" % "jackson-databind" % jacksonVersion,
      "com.fasterxml.jackson.core" % "jackson-annotations" % jacksonVersion,
      "com.fasterxml.jackson.dataformat" % "jackson-dataformat-toml" % jacksonVersion,
      "org.typelevel" %% "jawn-parser" % "1.7.0",
      "org.apache.commons" % "commons-compress" % "1.26.0",
      "org.apache.commons" % "commons-lang3" % "3.18.0",
    ) ++ Seq(
      "netty-buffer", "netty-codec", "netty-codec-http", "netty-codec-http2", "netty-common",
      "netty-handler", "netty-resolver", "netty-transport", "netty-transport-classes-epoll",
      "netty-transport-native-unix-common",
    ).map("io.netty" % _ % nettyVersion),
    assembly / assemblyMergeStrategy := {
      // Preserve ServiceLoader registrations (Flyway discovers its database
      // and plugin support via META-INF/services).
      case PathList("META-INF", "services", _*) => MergeStrategy.concat
      case PathList("META-INF", _*) => MergeStrategy.discard
      case "reference.conf" => MergeStrategy.concat
      case _ => MergeStrategy.first
    },
  )
