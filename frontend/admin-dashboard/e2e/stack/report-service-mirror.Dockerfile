FROM maven:3.8.7-eclipse-temurin-8 AS builder
WORKDIR /app
COPY --from=mirror maven-settings.xml /root/.m2/settings.xml
COPY services/report-service/pom.xml .
RUN mvn dependency:go-offline -B
COPY services/report-service/src/ src/
RUN mvn package -DskipTests -B
FROM eclipse-temurin:8-jre
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
RUN mkdir -p /tmp/reports
COPY --from=builder /app/target/report-service.jar app.jar
RUN useradd -r -u 1001 appuser && chown appuser:appuser /tmp/reports
USER appuser
EXPOSE 8091
ENTRYPOINT ["java", "-jar", "app.jar"]
