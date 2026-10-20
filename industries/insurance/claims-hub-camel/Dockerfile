# syntax=docker/dockerfile:1
FROM eclipse-temurin:21-jdk AS builder
# Optional mirror for the Maven distribution the wrapper downloads (empty = Maven Central).
ARG MVNW_REPOURL
WORKDIR /app
COPY .mvn/ .mvn/
COPY mvnw pom.xml ./
COPY src/ src/
# Optional build secret "m2settings" (a Maven settings.xml) for registry mirrors; never baked into the image.
RUN --mount=type=cache,target=/root/.m2/repository \
    --mount=type=secret,id=m2settings,target=/root/.m2/settings.xml,required=false \
    ./mvnw -B package -DskipTests

FROM eclipse-temurin:21-jre
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/* \
    && useradd -r -u 1001 appuser
WORKDIR /app
COPY --from=builder /app/target/claims-hub-camel.jar app.jar
USER 1001
EXPOSE 8092
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://localhost:8092/health || exit 1
ENTRYPOINT ["java", "-jar", "app.jar"]
