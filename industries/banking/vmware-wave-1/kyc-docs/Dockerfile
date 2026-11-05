# kyc-docs on the shared platform: Java 17, Spring Boot 3, plain HTTP on 8080
# (TLS at the ingress), uploads under KYC_UPLOAD_DIR, logs on stdout.
FROM docker.io/library/maven:3.9-eclipse-temurin-17@sha256:1a352420f7aba21f5ad08df31bab55f74c013fb491f1ae8ab1dd7ff9ed698584 AS test
WORKDIR /src
COPY pom.xml .
RUN mvn -q -B dependency:go-offline
COPY src src
RUN mvn -q -B test

FROM test AS build
RUN mvn -q -B package -DskipTests

FROM docker.io/library/eclipse-temurin:17-jre-jammy@sha256:b3054a20e1a851574cdb1692dd0db5310c647e62214a2a7abecbec1b9e3ae8f1
COPY --from=build /src/target/kyc-docs.jar /opt/kyc/kyc-docs.jar
USER 10001:10001
ENV KYC_UPLOAD_DIR=/var/kyc/uploads \
    JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=50 -XX:MaxMetaspaceSize=96m -Xss512k -XX:+UseSerialGC -XX:TieredStopAtLevel=1"
EXPOSE 8080
CMD ["java", "-jar", "/opt/kyc/kyc-docs.jar"]
