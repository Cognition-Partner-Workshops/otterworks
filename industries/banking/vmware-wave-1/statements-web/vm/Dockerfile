# Stand-in for the VM: Tomcat 8.5 on JRE 8, running as root, configuration
# and log directories laid out as they are on the host.
FROM docker.io/library/maven:3.9-eclipse-temurin-8@sha256:0f402712b7a469189cfea5ec69cdcadcb32b22aaf1ea62777ab925c3d8470175 AS build
ARG MAVEN_MIRROR=""
WORKDIR /src
RUN if [ -n "$MAVEN_MIRROR" ]; then mkdir -p /root/.m2 && printf '<settings><mirrors><mirror><id>m</id><mirrorOf>central</mirrorOf><url>%s</url></mirror></mirrors></settings>' "$MAVEN_MIRROR" > /root/.m2/settings.xml; fi
COPY pom.xml .
RUN mvn -q -B dependency:go-offline
COPY src src
RUN mvn -q -B package && mvn -q -B org.apache.maven.plugins:maven-dependency-plugin:3.6.1:copy \
      -Dartifact=org.postgresql:postgresql:42.2.27.jre7 -DoutputDirectory=/src/lib

FROM docker.io/library/tomcat:8.5-jre8@sha256:e3ca75a4b11560bfb30894c3fa5d066ff0105e2e8e1ad183711df97606321e51
COPY --from=build /src/lib/ /usr/local/tomcat/lib/
COPY vm/conf/context.xml /usr/local/tomcat/conf/context.xml
COPY vm/opt-app-conf/ /opt/app/conf/
RUN mkdir -p /var/log/statements && rm -rf /usr/local/tomcat/webapps/*
COPY --from=build /src/target/statements.war /usr/local/tomcat/webapps/statements.war
EXPOSE 8080
