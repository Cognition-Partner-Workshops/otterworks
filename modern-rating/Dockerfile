FROM mirror.gcr.io/library/maven:3.9.9-eclipse-temurin-21 AS build
WORKDIR /src
COPY pom.xml ./
RUN mvn -q -B dependency:go-offline
COPY src src
RUN mvn -q -B -DskipTests package

FROM mirror.gcr.io/library/eclipse-temurin:21-jre-alpine
WORKDIR /app
COPY --from=build /src/target/modern-rating.jar app.jar
EXPOSE 8092
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
