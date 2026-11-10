# Build stage. Maven Central rate-limits shared runners: pass MAVEN_MIRROR and/or
# MVNW_REPOURL as build args to use a mirror (docker-compose.insurance.yml forwards
# them from the environment). Nothing about the mirror is baked into the image.
FROM eclipse-temurin:21-jdk-jammy AS build
ARG MAVEN_MIRROR=
ARG MVNW_REPOURL=
WORKDIR /src
COPY .mvn .mvn
COPY mvnw pom.xml ./
RUN if [ -n "$MAVEN_MIRROR" ]; then \
      mkdir -p /root/.m2 && \
      printf '<settings><mirrors><mirror><id>mirror</id><mirrorOf>central</mirrorOf><url>%s</url></mirror></mirrors></settings>' \
        "$MAVEN_MIRROR" > /root/.m2/settings.xml; \
    fi && ./mvnw -q -B dependency:go-offline
COPY src src
RUN ./mvnw -q -B -DskipTests package

FROM eclipse-temurin:21-jre-jammy
WORKDIR /app
COPY --from=build /src/target/commission-service.jar /app/commission-service.jar
USER 1000:1000
EXPOSE 8000
# No curl in the JRE image; ask /actuator/health over bash's /dev/tcp.
HEALTHCHECK --interval=5s --timeout=5s --start-period=30s --retries=30 \
  CMD bash -c 'exec 3<>/dev/tcp/127.0.0.1/8000 && printf "GET /actuator/health HTTP/1.0\r\n\r\n" >&3 && grep -q "\"status\":\"UP\"" <&3'
ENTRYPOINT ["java", "-jar", "/app/commission-service.jar"]
