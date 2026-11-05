FROM docker.io/library/maven:3.9-eclipse-temurin-11@sha256:7bb84a451705605a47d24eb844d4d9ab03e33e131a507db76aafe25db3907f64 AS test
ARG MAVEN_MIRROR=""
WORKDIR /src
RUN if [ -n "$MAVEN_MIRROR" ]; then mkdir -p /root/.m2 && printf '<settings><mirrors><mirror><id>m</id><mirrorOf>central</mirrorOf><url>%s</url></mirror></mirrors></settings>' "$MAVEN_MIRROR" > /root/.m2/settings.xml; fi
COPY pom.xml .
COPY src src
RUN mvn -B package

FROM docker.io/library/eclipse-temurin:11-jre-jammy@sha256:ee9a1cf7847cb4b1f8176f4e96167f89a1148497500b75032575cb43dc69b42d
WORKDIR /app
COPY --from=test /src/target/rates-batch.jar /app/rates-batch.jar
ENV BUSINESS_TZ=Etc/UTC TZ=Etc/UTC
USER 10001
ENTRYPOINT ["java", "-XX:MaxRAMPercentage=70", "-jar", "/app/rates-batch.jar"]
