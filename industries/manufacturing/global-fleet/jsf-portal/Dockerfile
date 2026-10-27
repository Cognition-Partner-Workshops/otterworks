ARG BUILD_IMAGE=public.ecr.aws/docker/library/maven:3.9-eclipse-temurin-8
ARG RUN_IMAGE=public.ecr.aws/docker/library/tomcat:9.0-jre8-temurin
FROM ${BUILD_IMAGE} AS build
WORKDIR /src
ARG MAVEN_MIRROR=https://repo.maven.apache.org/maven2
RUN mkdir -p /root/.m2 && printf '<settings><mirrors><mirror><id>m</id><url>%s</url><mirrorOf>central</mirrorOf></mirror></mirrors></settings>' "$MAVEN_MIRROR" > /root/.m2/settings.xml
COPY pom.xml .
RUN mvn -q -B dependency:go-offline
COPY src ./src
RUN mvn -q -B package

FROM ${RUN_IMAGE}
RUN rm -rf /usr/local/tomcat/webapps/* \
 && sed -i 's/port="8080"/port="8080" relaxedQueryChars="[]|{}"/' /usr/local/tomcat/conf/server.xml
COPY --from=build /src/target/fleet.war /usr/local/tomcat/webapps/ROOT.war
ENV CATALINA_OPTS="-Xms128m -Xmx384m"
EXPOSE 8080
