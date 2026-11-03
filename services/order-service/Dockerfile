# Optional pull-through mirror, e.g. REGISTRY=mirror.gcr.io/library/
ARG REGISTRY=
FROM ${REGISTRY}maven:3.9-eclipse-temurin-21 AS build
# Optional Maven Central mirror, e.g. when the build host is rate-limited by repo.maven.apache.org.
ARG MAVEN_MIRROR_URL=""
WORKDIR /src
RUN if [ -n "$MAVEN_MIRROR_URL" ]; then mkdir -p /root/.m2 && printf '<settings><mirrors><mirror><id>mirror</id><mirrorOf>central</mirrorOf><url>%s</url></mirror></mirrors></settings>' "$MAVEN_MIRROR_URL" > /root/.m2/settings.xml; fi
COPY pom.xml .
RUN mvn -B -q dependency:go-offline
COPY src ./src
RUN mvn -B -q -DskipTests package

FROM ${REGISTRY}eclipse-temurin:21-jre-alpine
WORKDIR /app
RUN adduser -D -u 1001 app
COPY --from=build /src/target/order-service.jar /app/order-service.jar
USER 1001
EXPOSE 8080
ENV JAVA_OPTS="-XX:MaxRAMPercentage=75"
HEALTHCHECK --interval=10s --timeout=3s --start-period=40s CMD wget -q -O /dev/null http://127.0.0.1:8080/health || exit 1
ENTRYPOINT ["sh", "-c", "exec java $JAVA_OPTS -jar /app/order-service.jar"]
