FROM maven:3.9.9-eclipse-temurin-21 AS builder

ARG DD_JAVA_AGENT_VERSION=1.44.0

WORKDIR /app
COPY pom.xml .
# Download dependencies first for Docker layer caching
RUN mvn dependency:go-offline -B

# Datadog Java tracer, pinned. Fetched from Maven Central so the same mirror/proxy rules as the build apply.
RUN mvn -B -q dependency:copy \
      -Dartifact=com.datadoghq:dd-java-agent:${DD_JAVA_AGENT_VERSION}:jar \
      -DoutputDirectory=/app/agent \
 && mv /app/agent/dd-java-agent-${DD_JAVA_AGENT_VERSION}.jar /app/agent/dd-java-agent.jar

COPY src/ src/
RUN mvn package -DskipTests -B

FROM eclipse-temurin:21-jre

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN mkdir -p /tmp/reports

COPY --from=builder /app/target/report-service.jar app.jar
COPY --from=builder /app/agent/dd-java-agent.jar dd-java-agent.jar

RUN useradd -r -u 1001 appuser && chown appuser:appuser /tmp/reports
USER appuser

# Datadog unified service tagging + agent wiring. All overridable at runtime; the tracer reads these
# itself. With no agent reachable the tracer logs a warning and keeps buffering — the app still starts.
ENV DD_SERVICE=report-service \
    DD_ENV=local \
    DD_VERSION=0.1.0 \
    DD_AGENT_HOST=localhost \
    DD_TRACE_AGENT_PORT=8126 \
    DD_DOGSTATSD_PORT=8125 \
    DD_LOGS_INJECTION=true

EXPOSE 8091

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8091/health || exit 1

ENTRYPOINT ["java", "-javaagent:/app/dd-java-agent.jar", "-jar", "app.jar"]
