FROM mirror.gcr.io/library/debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends gnucobol3 make \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /estate/cobol
COPY . .
RUN make build
RUN groupadd --system --gid 1000 rating \
    && useradd --system --uid 1000 --gid rating --key SYS_UID_MAX=1000 \
        --no-create-home --shell /usr/sbin/nologin rating
USER 1000:1000
ENTRYPOINT ["./run.sh"]
