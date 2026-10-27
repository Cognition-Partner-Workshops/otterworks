ARG BUILD_IMAGE=public.ecr.aws/docker/library/maven:3.9-eclipse-temurin-17
ARG RUN_IMAGE=public.ecr.aws/docker/library/eclipse-temurin:17-jre-alpine
FROM ${BUILD_IMAGE} AS build
WORKDIR /src
ARG MAVEN_MIRROR=https://repo.maven.apache.org/maven2
RUN mkdir -p /root/.m2 && printf '<settings><mirrors><mirror><id>m</id><url>%s</url><mirrorOf>central</mirrorOf></mirror></mirrors></settings>' "$MAVEN_MIRROR" > /root/.m2/settings.xml
COPY pom.xml .
RUN mvn -q -B -Pde dependency:go-offline
COPY src ./src
# The jar is the same for both countries; SPRING_PROFILES_ACTIVE picks uk or de at run time.
RUN mvn -q -B -Pde -Dmaven.test.skip=true package

FROM ${RUN_IMAGE}
RUN addgroup -S fleet && adduser -S -G fleet -u 10001 fleet
WORKDIR /app
COPY --from=build /src/target/fleet-service-*.jar /app/fleet-service.jar
USER 10001
ENV JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=75"
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/fleet-service.jar"]
