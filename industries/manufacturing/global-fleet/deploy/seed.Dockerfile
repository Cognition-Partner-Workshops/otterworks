ARG BUILD_IMAGE=public.ecr.aws/docker/library/python:3.12-alpine
ARG RUN_IMAGE=public.ecr.aws/docker/library/postgres:16-alpine
FROM ${BUILD_IMAGE} AS unload
COPY deploy/unload_to_sql.py /unload_to_sql.py
COPY mainframe/unload /unload
RUN python3 /unload_to_sql.py /unload > /uk_unload.sql

FROM ${RUN_IMAGE}
COPY seed/jsf/001_schema.sql seed/jsf/002_seed.sql deploy/after-seed.sql /seed/
COPY --from=unload /uk_unload.sql /seed/
