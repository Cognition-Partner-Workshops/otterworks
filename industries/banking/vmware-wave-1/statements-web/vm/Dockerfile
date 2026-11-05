# Hardened VM stand-in; keep the existing javax.servlet application contract.
FROM docker.io/library/maven:3.9-eclipse-temurin-17@sha256:1a352420f7aba21f5ad08df31bab55f74c013fb491f1ae8ab1dd7ff9ed698584 AS test
ARG MAVEN_MIRROR=""
WORKDIR /src
RUN if [ -n "$MAVEN_MIRROR" ]; then mkdir -p /root/.m2 && printf '<settings><mirrors><mirror><id>m</id><mirrorOf>central</mirrorOf><url>%s</url></mirror></mirrors></settings>' "$MAVEN_MIRROR" > /root/.m2/settings.xml; fi
COPY pom.xml .
RUN mvn -q -B dependency:go-offline
COPY src src
RUN mvn -q -B test

FROM test AS build
RUN mvn -q -B package && mvn -q -B org.apache.maven.plugins:maven-dependency-plugin:3.6.1:copy \
      -Dartifact=org.postgresql:postgresql:42.2.27.jre7 -DoutputDirectory=/src/lib
RUN mkdir /src/expanded && cd /src/expanded && jar -xf /src/target/statements.war

FROM docker.io/library/tomcat:9.0-jre17-temurin-jammy@sha256:729c7e1c48be985cdfc1fac9f50f1bcb0391ae911479a5b21574f2820e805845 AS runtime
COPY --from=build /src/lib/ /usr/local/tomcat/lib/
COPY vm/conf/context.xml /usr/local/tomcat/conf/context.xml
COPY vm/conf/logging.properties /usr/local/tomcat/conf/logging.properties
COPY vm/opt-app-conf/ /opt/app/conf/
RUN rm -rf /usr/local/tomcat/webapps/* \
    && mkdir -p /usr/local/tomcat/temp /usr/local/tomcat/work \
    && chown -R 10001:10001 /usr/local/tomcat/temp /usr/local/tomcat/work
COPY --from=build /src/expanded/ /usr/local/tomcat/webapps/statements/
USER 10001:10001
EXPOSE 8080
