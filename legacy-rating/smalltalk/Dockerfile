FROM mirror.gcr.io/library/debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl unzip libcairo2 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/pharo
RUN curl -fsSL https://get.pharo.org/64/120+vm | bash
ENV PHARO=/opt/pharo/pharo PHARO_IMAGE=/opt/pharo/Pharo.image PHARO_WORK=/opt/insrating
WORKDIR /estate/smalltalk
COPY . .
RUN groupadd --gid 1000 pharo \
    && useradd --uid 1000 --gid pharo --create-home pharo \
    && install -d -o pharo -g pharo "$PHARO_WORK"
USER pharo:pharo
RUN ./run.sh build
EXPOSE 8091
ENTRYPOINT ["./run.sh"]
CMD ["screen", "8091"]
