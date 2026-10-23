# report-service characterization suite

Pins the behaviour of `services/report-service` **as it runs today** (Java 8, Spring Boot 2.5.15,
PostgreSQL, `TZ=America/Chicago` as in `docker-compose.yml` and the Helm values) so the Java 17 /
Spring Boot 3 upgrade can be checked against it. The suite is black-box: Python + HTTP against the
running containers, and the CSV / Excel / PDF files they serve. Nothing in it depends on JUnit,
Spring or any JVM API, so it runs unchanged after the upgrade.

## Stack (`docker-compose.yml`)

| service | what |
|---|---|
| `postgres` | `postgres:15-alpine`; `otterworks_reports` (JPA `reports` table) and `otterworks_archive` (`migration/target/postgresql/*.sql` + `fixtures/postgres/archive-fixture.sql.in`) |
| `db2` | `icr.io/db2_community/db2:11.5.9.0` (the image of `infrastructure/helm/db2-archive`), database `CHARDB`, `migration/source/db2/ddl/*.sql` + `fixtures/db2/fixture.sql` |
| `upstream-stub` | deterministic analytics / audit / auth endpoints (`stub/upstream_stub.py`) |
| `report-off` :18091 | `ARCHIVE_STORE` unset, upstreams = stub |
| `report-db2` :18092 | `ARCHIVE_STORE=db2`, upstreams unreachable (pins the fallbacks) |
| `report-pg` :18093 | `ARCHIVE_STORE=postgresql`, `mig.*` ledger, upstreams unreachable |

The three report-service containers are the image built from `../Dockerfile`, with the same
`read_only` + `/tmp` tmpfs settings as the root Compose file. The archive fixture is one data set
rendered for both stores by `fixtures/gen_fixtures.py` (Db2 CHAR padding, `TIMESTAMP(12)`, CCSID 037
`FOR BIT DATA`; PostgreSQL 6+6 digit timestamp split).

## Run

```bash
cd services/report-service/characterization
./run.sh up        # builds the image from ../Dockerfile; Db2 first start takes ~3-5 min
./run.sh test      # compares against baseline/snapshots
./run.sh down
```

If `docker build` cannot reach Maven Central (HTTP 429 from shared egress), run `./run.sh image`
first and then `REPORT_IMAGE=report-service:characterization ./run.sh up`: the jar is built with
the Dockerfile's own builder image and command (host `~/.m2/settings.xml` mirrors apply) and fed to
the unmodified runtime stage.

## Baseline

`baseline/snapshots/*.json` were recorded with `./run.sh record` on the unmodified Java 8 code;
`baseline/java8-run.txt` is the passing run. After the upgrade run `./run.sh test` **without**
re-recording; every differing snapshot is a parity row (identical / accepted difference / failed).
Volatile values are checked and then replaced by placeholders: report ids, `createdAt`/`completedAt`
(format `yyyy-MM-dd'T'HH:mm:ss.SSS+00:00` asserted), file-name stamps and "Generated" lines
(asserted to be the current **UTC** time), reconciliation `generated_at`.

## What is pinned

- `HealthController` (`/health`, `/health/archive` per store), actuator health/info/prometheus,
  security headers, SpringFox `/v2/api-docs` path list, default error bodies (404/405/400).
- `ReportController` `/api/v1/reports`: 202 create body, validation 400s, request date parsing
  (ISO, date-only, epoch millis, offsets) and the JSON date format, list filters, download,
  delete lifecycle, unknown ids, `/api/v1/reports/scheduled` (no such endpoint: 400 on GET, 405 otherwise).
- Generated files: CSV (banner rows, quoting, encoding, header/data rows), Excel (sheets, Summary
  cells, merged title, Data rows, auto-filter), PDF (page size/rotation, text lines), file names.
- `ReportDateUtils` through those outputs: ISO (`window_from`/`window_to` echoed by the stub),
  display (`Period` / `Generated` lines, Excel Summary) and file-name stamps are UTC although the
  JVM runs with `TZ=America/Chicago`; the request window starts at 03:30 UTC so a local-zone format
  would show the previous day.
- `ArchiveController` on all three prefixes with `ARCHIVE_STORE` unset (404 + hint), `db2` and
  `postgresql` (document, `?raw=true`, `/hash`, padded and unknown ids); cross-store equality of the
  default document; `BusinessHash` differences caused by key padding.
- `ReconciliationController` JSON / CSV / HTML on both prefixes: 404 bodies for unset and `db2`,
  run list, `latest`, per-run JSON, CSV and HTML for `postgresql`, unknown and foreign-namespace runs.
