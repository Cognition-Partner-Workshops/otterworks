FROM eclipse-temurin:25-jdk-noble AS builder

WORKDIR /app
COPY gradlew build.gradle.kts settings.gradle.kts ./
COPY gradle ./gradle
RUN ./gradlew dependencies --no-daemon || true

COPY src ./src
RUN ./gradlew shadowJar --no-daemon

FROM eclipse-temurin:25-jre-noble
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /app/build/libs/*-all.jar app.jar

RUN useradd -r -u 1001 appuser
USER appuser

EXPOSE 8086
HEALTHCHECK --interval=10s --timeout=3s CMD curl -f http://localhost:8086/health || exit 1
ENTRYPOINT ["java", "-jar", "app.jar"]
