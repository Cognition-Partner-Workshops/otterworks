# Stand-in for kyc-01: JRE 11, a self-signed certificate in a local keystore
# made the way the VM's was (keytool, ten years), uploads on local disk.
# The keystore and its password are synthetic and generated on first start
# (vm/start.sh), so the image carries neither.
FROM docker.io/library/maven:3.9-eclipse-temurin-11@sha256:7bb84a451705605a47d24eb844d4d9ab03e33e131a507db76aafe25db3907f64 AS test
ARG MAVEN_MIRROR=""
WORKDIR /src
RUN if [ -n "$MAVEN_MIRROR" ]; then mkdir -p /root/.m2 && printf '<settings><mirrors><mirror><id>m</id><mirrorOf>central</mirrorOf><url>%s</url></mirror></mirrors></settings>' "$MAVEN_MIRROR" > /root/.m2/settings.xml; fi
COPY pom.xml .
COPY src src
RUN mvn -q -B test

FROM test AS build
RUN mvn -q -B package -DskipTests

FROM docker.io/library/eclipse-temurin:11-jre-jammy@sha256:ee9a1cf7847cb4b1f8176f4e96167f89a1148497500b75032575cb43dc69b42d
RUN mkdir -p /etc/kyc /var/kyc/uploads /var/log/kyc /opt/kyc \
 && chown 10001:10001 /etc/kyc /var/kyc/uploads /var/log/kyc && chmod 0700 /etc/kyc
COPY --from=build /src/target/kyc-docs.jar /opt/kyc/kyc-docs.jar
COPY vm/start.sh /opt/kyc/start.sh
USER 10001:10001
EXPOSE 8443
CMD ["/bin/sh", "/opt/kyc/start.sh"]
