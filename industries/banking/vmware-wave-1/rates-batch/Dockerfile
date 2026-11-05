# rates-batch on the platform: unit tests first, then a JRE 17 image that runs
# the job once and exits. Scheduling, the business-date zone and the spools come
# from the chart (deploy/values.yaml); logs go to stdout and stderr.
FROM docker.io/library/maven:3.9-eclipse-temurin-17@sha256:1a352420f7aba21f5ad08df31bab55f74c013fb491f1ae8ab1dd7ff9ed698584 AS test
ARG MAVEN_MIRROR=""
WORKDIR /src
RUN if [ -n "$MAVEN_MIRROR" ]; then mkdir -p /root/.m2 && printf '<settings><mirrors><mirror><id>m</id><mirrorOf>central</mirrorOf><url>%s</url></mirror></mirrors></settings>' "$MAVEN_MIRROR" > /root/.m2/settings.xml; fi
COPY pom.xml .
COPY src src
RUN mvn -B -q test

FROM test AS build
RUN mvn -B -q -DskipTests package

FROM docker.io/library/eclipse-temurin:17-jre-jammy@sha256:b3054a20e1a851574cdb1692dd0db5310c647e62214a2a7abecbec1b9e3ae8f1
COPY --from=build /src/target/rates-batch.jar /app/rates-batch.jar
USER 10001:10001
ENTRYPOINT ["java", "-XX:MaxRAMPercentage=75", "-jar", "/app/rates-batch.jar"]
