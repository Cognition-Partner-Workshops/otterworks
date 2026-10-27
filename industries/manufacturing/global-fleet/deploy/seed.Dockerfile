ARG RUN_IMAGE=public.ecr.aws/docker/library/postgres:16-alpine
FROM ${RUN_IMAGE}
COPY seed/jsf/001_schema.sql seed/jsf/002_seed.sql /seed/
