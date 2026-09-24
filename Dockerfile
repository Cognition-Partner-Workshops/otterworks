# LEGACY: Uses JDK 8 (target: JDK 17+ or 21+)
# Maven build instead of Gradle (matches legacy Java enterprise pattern)
FROM maven:3.9.9-eclipse-temurin-21 AS builder

WORKDIR /app
COPY pom.xml .
# Download dependencies first for Docker layer caching
RUN mvn dependency:go-offline -B

COPY src/ src/
RUN mvn package -DskipTests -B

# Download Datadog Java APM agent
FROM curlimages/curl:8.7.1 AS agent-downloader
ARG DD_JAVA_AGENT_VERSION=1.37.1
RUN curl -Lo /tmp/dd-java-agent.jar \
    "https://github.com/DataDog/dd-trace-java/releases/download/v${DD_JAVA_AGENT_VERSION}/dd-java-agent-${DD_JAVA_AGENT_VERSION}.jar"

# LEGACY: JRE 8 runtime (target: eclipse-temurin:17-jre or 21-jre)
FROM eclipse-temurin:21-jre

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN mkdir -p /tmp/reports

COPY --from=builder /app/target/report-service.jar app.jar
COPY --from=agent-downloader /tmp/dd-java-agent.jar /app/dd-java-agent.jar

RUN useradd -r -u 1001 appuser && chown appuser:appuser /tmp/reports
USER appuser

ENV DD_SERVICE=report-service
ENV DD_ENV=local
ENV DD_VERSION=0.1.0
ENV DD_AGENT_HOST=localhost
ENV DD_TRACE_AGENT_PORT=8126
ENV DD_LOGS_INJECTION=true

EXPOSE 8091

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8091/health || exit 1

ENTRYPOINT ["java", "-javaagent:/app/dd-java-agent.jar", "-jar", "app.jar"]
