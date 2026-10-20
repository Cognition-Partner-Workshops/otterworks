# fx-report on the platform standard (platform/standards at c56cbe8f6f4c): python-3.12-slim from base-images.yaml.
# Unit tests: docker build --target test .   Image: docker build -t fx-report .
# Run: docker run --read-only --tmpfs /tmp -p 8080:8080 -v <rates dir>:/mnt/rates-out:ro fx-report
FROM docker.io/library/python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS test
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /src
COPY app/ app/
COPY lib/ lib/
COPY tests/golden/ tests/golden/
COPY tests/characterization/report_page.py tests/characterization/
WORKDIR /src/app
USER 10001
RUN python -m unittest -v test_rates test_server

FROM docker.io/library/python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
WORKDIR /app
COPY --from=test /src/app/server.py /src/app/rates.py ./
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 RATES_DIR=/mnt/rates-out PORT=8080
USER 10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT', '8080'), timeout=2)"]
CMD ["python", "server.py"]
