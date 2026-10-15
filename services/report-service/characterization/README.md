# report-service characterization tests

HTTP-level tests that pin the behaviour of a **running** report-service (status codes, headers,
JSON bodies, error shapes, generated CSV/PDF/XLSX downloads, feature-off archive/reconciliation
responses). They were written and passed against the Java 8 / Spring Boot 2.5.15 build and are
meant to be rerun unchanged against later builds.

```bash
# PostgreSQL + the service from its own Dockerfile; no analytics/audit/auth services, ARCHIVE_STORE unset
docker network create rs-char
docker run -d --name rs-pg --network rs-char -e POSTGRES_DB=otterworks_reports \
  -e POSTGRES_USER=otterworks -e POSTGRES_PASSWORD=otterworks_dev postgres:15-alpine
docker build -t report-service:local services/report-service
docker run -d --name rs --network rs-char -p 18091:8091 \
  --read-only --tmpfs /tmp --security-opt no-new-privileges:true \
  -e DB_HOST=rs-pg -e DB_PORT=5432 -e DB_NAME=otterworks_reports \
  -e DB_USER=otterworks -e DB_PASSWORD=otterworks_dev -e REPORT_OUTPUT_DIR=/tmp/reports -e TZ=UTC \
  report-service:local

REPORT_SERVICE_URL=http://localhost:18091 services/report-service/characterization/run.sh
```

`run.sh` uses `uv` to provide Python 3.12 + pytest; any Python 3.8+ with pytest works too:
`REPORT_SERVICE_URL=... pytest characterization/test_characterization.py`.
