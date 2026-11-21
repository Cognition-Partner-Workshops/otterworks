FROM gradle:8.6-jdk17 AS builder
WORKDIR /app
COPY services/auth-service/ .
COPY --from=mirror gradle-init.gradle /home/gradle/.gradle/init.gradle
RUN gradle bootJar --no-daemon
FROM eclipse-temurin:17-jre-jammy
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /app/build/libs/*.jar app.jar
RUN useradd -r -u 1001 appuser
USER appuser
EXPOSE 8081
ENTRYPOINT ["java", "-jar", "app.jar"]
