FROM eclipse-temurin:21-jre-alpine
ARG DOMAIN
RUN addgroup -S integration && adduser -S -G integration integration
WORKDIR /app
COPY ${DOMAIN}/target/${DOMAIN}-1.0.0.jar /app/app.jar
USER integration
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
