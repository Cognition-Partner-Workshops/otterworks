FROM docker.io/library/maven:3.9-eclipse-temurin-8@sha256:0f402712b7a469189cfea5ec69cdcadcb32b22aaf1ea62777ab925c3d8470175 AS test
ARG MAVEN_MIRROR=https://maven-central.storage-download.googleapis.com/maven2/
WORKDIR /src
RUN mkdir -p /root/.m2 && printf '<settings><mirrors><mirror><id>central-mirror</id><mirrorOf>central</mirrorOf><url>%s</url></mirror></mirrors></settings>' "$MAVEN_MIRROR" > /root/.m2/settings.xml
COPY pom.xml .
RUN mvn -B -q dependency:go-offline
COPY src src
RUN mvn -B package

FROM docker.io/library/tomcat:9.0-jre8-temurin-jammy@sha256:9b9b6ad5364db67f511d0e1501b4e4a50d4cc5a90dd03765feb0c4d04b38cd00
RUN rm -rf /usr/local/tomcat/webapps/* /usr/local/tomcat/webapps.dist && mkdir -p /usr/local/tomcat/webapps/statements /usr/local/tomcat/webapps/ROOT /usr/local/tomcat/conf/Catalina/localhost
COPY --from=test /src/target/statements/ /usr/local/tomcat/webapps/statements/
COPY deploy/tomcat/server.xml deploy/tomcat/logging.properties /usr/local/tomcat/conf/
COPY deploy/tomcat/health.jsp /usr/local/tomcat/webapps/ROOT/health.jsp
COPY deploy/tomcat/root-web.xml /usr/local/tomcat/webapps/ROOT/WEB-INF/web.xml
ENV JAVA_OPTS="-Xms32m -Xmx128m -XX:MaxMetaspaceSize=64m -Duser.timezone=UTC -Duser.language=en -Duser.country=US -Dfile.encoding=UTF-8"
USER 10001:10001
EXPOSE 8080
CMD ["catalina.sh", "run"]
