# Stand-in for kyc-01: JRE 11, a self-signed certificate in a local keystore
# made the way the VM's was (keytool, ten years), uploads on local disk.
FROM docker.io/library/maven:3.9-eclipse-temurin-11 AS build
ARG MAVEN_MIRROR=""
WORKDIR /src
RUN if [ -n "$MAVEN_MIRROR" ]; then mkdir -p /root/.m2 && printf '<settings><mirrors><mirror><id>m</id><mirrorOf>central</mirrorOf><url>%s</url></mirror></mirrors></settings>' "$MAVEN_MIRROR" > /root/.m2/settings.xml; fi
COPY pom.xml .
COPY src src
RUN mvn -q -B package -DskipTests

FROM docker.io/library/eclipse-temurin:11-jre
RUN mkdir -p /etc/kyc /var/kyc/uploads /var/log/kyc /opt/kyc \
 && keytool -genkeypair -alias kyc -keyalg RSA -keysize 2048 -validity 3650 -dname "CN=kyc-01" \
      -storetype PKCS12 -keystore /etc/kyc/keystore.p12 -storepass changeit -keypass changeit
COPY --from=build /src/target/kyc-docs.jar /opt/kyc/kyc-docs.jar
EXPOSE 8443
CMD ["java", "-Xmx512m", "-jar", "/opt/kyc/kyc-docs.jar"]
