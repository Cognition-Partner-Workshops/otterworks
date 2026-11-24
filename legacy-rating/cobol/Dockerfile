FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends gnucobol3 make \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /estate/cobol
COPY . .
RUN make build
ENTRYPOINT ["./run.sh"]
