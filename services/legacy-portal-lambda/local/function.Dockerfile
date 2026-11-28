# Builds one context module of services/legacy-portal-lambda and runs its handler under the
# AWS Lambda Runtime Interface Emulator bundled in the official Java 21 base image.
# Build context: services/legacy-portal-lambda; --build-arg CONTEXT=announcements|preferences|feedback.
FROM maven:3.9.9-eclipse-temurin-21@sha256:3a4ab3276a087bf276f79cae96b1af04f53731bec53fb2e651aca79e4b10211e AS build
ARG CONTEXT
WORKDIR /src
COPY ${CONTEXT}/pom.xml pom.xml
COPY ${CONTEXT}/src src
RUN mvn -B -q package && mkdir /out \
    && cp "$(ls target/*.jar | grep -v '/original-' | head -1)" /out/function.jar

FROM public.ecr.aws/lambda/java:21@sha256:c434dda008c7862d7188d44b5ee1ae579f8b878b04acb6e30ae1f0a2a87ebb6d
COPY --from=build /out/function.jar ${LAMBDA_TASK_ROOT}/lib/function.jar
