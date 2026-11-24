FROM mirror.gcr.io/library/debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends gnucobol3 make \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /estate/cobol
COPY Makefile RATEPREM.cbl run.sh ./
COPY copybooks/POLREC.cpy copybooks/RATEOUT.cpy copybooks/RATETBL.cpy ./copybooks/
RUN make build
ENTRYPOINT ["./run.sh"]
