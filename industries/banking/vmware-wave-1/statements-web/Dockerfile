FROM docker.io/library/maven:3.9-eclipse-temurin-17@sha256:1a352420f7aba21f5ad08df31bab55f74c013fb491f1ae8ab1dd7ff9ed698584 AS test
WORKDIR /src
COPY pom.xml .
COPY src src
COPY vm/opt-app-conf vm/opt-app-conf
RUN mvn -B test package && mkdir expanded && cd expanded && jar xf ../target/statements.war

FROM docker.io/library/tomcat:9.0-jre17-temurin-jammy@sha256:729c7e1c48be985cdfc1fac9f50f1bcb0391ae911479a5b21574f2820e805845 AS runtime
RUN rm -rf /usr/local/tomcat/webapps/*
COPY --from=test /src/expanded/ /usr/local/tomcat/webapps/ROOT/
COPY deploy/server.xml /usr/local/tomcat/conf/server.xml
COPY deploy/context.xml /usr/local/tomcat/conf/context.xml
COPY deploy/logging.properties /usr/local/tomcat/conf/logging.properties
ENV CATALINA_OPTS="-Djava.io.tmpdir=/tmp -Duser.timezone=UTC"
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s CMD curl -fsS http://127.0.0.1:8080/health || exit 1
CMD ["catalina.sh", "run"]
