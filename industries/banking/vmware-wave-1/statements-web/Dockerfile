# statements-web on the platform Tomcat base. The test stage runs the unit
# tests and builds the WAR; the runtime stage serves it exploded so the root
# filesystem can stay read-only.
FROM docker.io/library/maven:3.9-eclipse-temurin-17@sha256:1a352420f7aba21f5ad08df31bab55f74c013fb491f1ae8ab1dd7ff9ed698584 AS test
ARG MAVEN_MIRROR=""
WORKDIR /src
RUN if [ -n "$MAVEN_MIRROR" ]; then mkdir -p /root/.m2 && printf '<settings><mirrors><mirror><id>m</id><mirrorOf>central</mirrorOf><url>%s</url></mirror></mirrors></settings>' "$MAVEN_MIRROR" > /root/.m2/settings.xml; fi
COPY pom.xml .
RUN mvn -q -B dependency:go-offline
COPY src src
RUN mvn -B package

FROM docker.io/library/tomcat:9.0-jre17-temurin-jammy@sha256:729c7e1c48be985cdfc1fac9f50f1bcb0391ae911479a5b21574f2820e805845
RUN rm -rf /usr/local/tomcat/webapps /usr/local/tomcat/webapps.dist \
    && mkdir -p /usr/local/tomcat/webapps /usr/local/tomcat/conf/Catalina/localhost
COPY tomcat/server.xml tomcat/logging.properties /usr/local/tomcat/conf/
COPY tomcat/rewrite.config /usr/local/tomcat/conf/Catalina/localhost/
COPY --from=test /src/target/statements /usr/local/tomcat/webapps/statements
ENV CATALINA_OPTS="-XX:MaxRAMPercentage=60 -XX:+ExitOnOutOfMemoryError"
USER 10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s CMD curl -fsS http://127.0.0.1:8080/health || exit 1
CMD ["catalina.sh", "run"]
