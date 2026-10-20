# Stand-in for rates-01: JRE 11, cron in the foreground, spool and log
# directories where the host keeps them. Runs as root, like the VM.
FROM docker.io/library/maven:3.9-eclipse-temurin-11 AS build
ARG MAVEN_MIRROR=""
WORKDIR /src
RUN if [ -n "$MAVEN_MIRROR" ]; then mkdir -p /root/.m2 && printf '<settings><mirrors><mirror><id>m</id><mirrorOf>central</mirrorOf><url>%s</url></mirror></mirrors></settings>' "$MAVEN_MIRROR" > /root/.m2/settings.xml; fi
COPY pom.xml .
COPY src src
RUN mvn -q -B package

FROM docker.io/library/eclipse-temurin:11-jre
RUN apt-get update && apt-get install -y --no-install-recommends cron && rm -rf /var/lib/apt/lists/* \
 && mkdir -p /opt/rates/bin /opt/rates/lib /var/spool/rates/in /var/spool/rates/out /var/log/rates \
 && ln -s /opt/java/openjdk /usr/lib/jvm/java-11 2>/dev/null || mkdir -p /usr/lib/jvm && ln -sf /opt/java/openjdk /usr/lib/jvm/java-11
COPY --from=build /src/target/rates-batch.jar /opt/rates/lib/rates-batch.jar
COPY vm/run-rates.sh /opt/rates/bin/run-rates.sh
COPY vm/crontab /etc/cron.d/rates
RUN sed -i 's#^0 2 \* \* \* #0 2 * * * root #' /etc/cron.d/rates && chmod 0644 /etc/cron.d/rates
CMD ["cron", "-f"]
