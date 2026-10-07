# preferences-service parity report

Before: the monolith built from `main` at `af476560` (image `sha256:f78d918bd015`), Compose
`services/legacy-portal/docker-compose.onprem.yml` with an empty database. The full corpus
(`services/legacy-portal/parity/requests.json`, 95 cases, checksums verified) was recorded with
`parity/record.py` into `parity/transcripts/monolith-main.json`.

After: this branch, `docker-compose.portal.yml` with empty databases. `parity/run.sh` replays the
same corpus with `services/legacy-portal/parity/replay.py --stage full --strict-media-type`
through the strangler edge (`localhost:8095`) and compares status, media type and body against
the transcript. Timestamps are normalised by `replay.py`, nothing else. Run at 2026-10-07T13:35Z and re-run at
2026-10-07T13:45Z after the review follow-ups (edge no longer forwards the client `Host`), and again
after the readiness change (image rebuilt); same result each time.

Local builds pulled Maven artifacts from Google's Maven Central mirror because Maven Central was
rate-limiting this host (HTTP 429). The Dockerfiles are otherwise the committed ones.

## Summary

| what was compared | before | after | result |
|---|---|---|---|
| fresh recording on `main` vs the checked-in `java-reference.json` | 95 cases | 95/95 identical | identical |
| preferences cases, replayed through the edge | 20 responses recorded from the monolith on `main` | 20/20 identical, 0 different | identical |
| common cases, replayed through the edge | 10 responses recorded from the monolith on `main` | 10/10 identical, 0 different | identical |
| announcements cases, replayed through the edge | 36 responses recorded from the monolith on `main` | 36/36 identical, 0 different | identical |
| feedback cases, replayed through the edge | 29 responses recorded from the monolith on `main` | 29/29 identical, 0 different | identical |
| `preferences-service` `mvn verify` (Java 21, Temurin) | n/a (new service) | 11 run, 0 failed | identical |
| `legacy-portal` `mvn verify` | `main`: 16 run, 1 failed (`AnnouncementServiceTest.listPublishedReturnsOnlyPublishedNewestFirst`) | 14 run, 1 failed (same test; the 2 `UserPreferenceServiceTest` cases moved to preferences-service) | failed (fails the same way on `main`: `LegacyPortalApplicationTest` commits a published "Release" announcement into the shared in-memory H2 before this test runs; not changed here) |
| `helm lint --strict` (with `image.tag` and `config.SPRING_DATASOURCE_URL` set) | n/a | 1 chart linted, 0 failed | identical |
| `helm template \| kubeconform -strict`, chart defaults (ingress off) | n/a | 4 resources, 4 valid | identical |
| same, with `ingress.enabled=true` and `--api-versions monitoring.coreos.com/v1` (adds Ingress and ServiceMonitor, CRD schema) | n/a | 6 resources, 6 valid | identical |
| chart with `service.type=LoadBalancer` | n/a | render refused | identical |
| chart with the postgres profile and no `config.SPRING_DATASOURCE_URL` | n/a | render refused | identical |
| image runtime user and `HEALTHCHECK` | legacy-portal: uid 1001, `curl -f /health` | preferences-service: uid 1001, `curl -f http://localhost:8098/health` | identical |
| chart probes | legacy-portal chart n/a; `report-service` chart: liveness and readiness both on `/health` | liveness `/health`, readiness `/actuator/health/readiness` (readiness state + `db`) | accepted difference: requested so a database outage takes pods out of the Service without restarting them |
| Compose stack, `preferences-db` stopped | n/a | `/health` 200, `/actuator/health/liveness` 200, `/actuator/health/readiness` 503 (after the 30 s Hikari connection timeout; kubelet already counts the probe's timeout as a failure); 200 again once the database is back | identical to the intended behaviour |
| README cutover: `pg_dump` copy, then the row-count gate, legacy-portal-db seeded with 3 rows | n/a | copy loads 3 rows, gate passes (3 = 3), copied row served through the edge; with a 4th legacy row added the gate prints `row counts differ` and exits 1 | identical to the intended behaviour |

## Which upstream answered

| route | expected upstream | X-Served-By | result |
|---|---|---|---|
| `GET /health` | legacy-portal | legacy-portal | identical |
| `GET /api/announcements` | legacy-portal | legacy-portal | identical |
| `GET /api/feedback/average-rating` | legacy-portal | legacy-portal | identical |
| `GET /api/preferences/alice` | preferences-service | preferences-service | identical |
| `GET /api/preferences` | preferences-service | preferences-service | identical |
| `GET /API/preferences/alice` | legacy-portal | legacy-portal | identical |
| `GET /api/preferencesX` | legacy-portal | legacy-portal | identical |
| `GET /api/preferences/alice` direct to legacy-portal | 404 | 404 | identical |

## Replay summary (`replay.py`)

| Context | Cases in corpus | Cases run | Identical | Different | First divergence | Result |
|---|---|---|---|---|---|---|
| common | 10 | 10 | 10 | 0 | - | all identical |
| announcements | 36 | 36 | 36 | 0 | - | all identical |
| preferences | 20 | 20 | 20 | 0 | - | all identical |
| feedback | 29 | 29 | 29 | 0 | - | all identical |

## Preferences, case by case

| case | request | before (monolith on `main`) | after (through the edge) | result |
|---|---|---|---|---|
| pref-01 | `GET /api/preferences/newuser` | 200 application/json `{"userId": "newuser", "theme": "light", "locale": "en-US", "emailNotifications": true}` | 200 application/json `{"userId": "newuser", "theme": "light", "locale": "en-US", "emailNotifications": true}` | identical |
| pref-02 | `PUT /api/preferences/u1` | 200 application/json `{"userId": "u1", "theme": "dark", "locale": "fr-FR", "emailNotifications": false}` | 200 application/json `{"userId": "u1", "theme": "dark", "locale": "fr-FR", "emailNotifications": false}` | identical |
| pref-03 | `GET /api/preferences/u1` | 200 application/json `{"userId": "u1", "theme": "dark", "locale": "fr-FR", "emailNotifications": false}` | 200 application/json `{"userId": "u1", "theme": "dark", "locale": "fr-FR", "emailNotifications": false}` | identical |
| pref-04 | `PUT /api/preferences/u1` | 200 application/json `{"userId": "u1", "theme": "light", "locale": "en-US", "emailNotifications": false}` | 200 application/json `{"userId": "u1", "theme": "light", "locale": "en-US", "emailNotifications": false}` | identical |
| pref-05 | `GET /api/preferences/u1` | 200 application/json `{"userId": "u1", "theme": "light", "locale": "en-US", "emailNotifications": false}` | 200 application/json `{"userId": "u1", "theme": "light", "locale": "en-US", "emailNotifications": false}` | identical |
| pref-06 | `PUT /api/preferences/u2` | 400 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 400, "error": "Bad...` | 400 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 400, "error": "Bad...` | identical |
| pref-07 | `PUT /api/preferences/u2` | 400 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 400, "error": "Bad...` | 400 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 400, "error": "Bad...` | identical |
| pref-08 | `PUT /api/preferences/u2` | 400 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 400, "error": "Bad...` | 400 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 400, "error": "Bad...` | identical |
| pref-09 | `PUT /api/preferences/u2` | 400 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 400, "error": "Bad...` | 400 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 400, "error": "Bad...` | identical |
| pref-10 | `PUT /api/preferences/u2` | 415 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 415, "error": "Uns...` | 415 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 415, "error": "Uns...` | identical |
| pref-11 | `PUT /api/preferences/u2` | 200 application/json `{"userId": "u2", "theme": "dark", "locale": "de-DE", "emailNotifications": true}` | 200 application/json `{"userId": "u2", "theme": "dark", "locale": "de-DE", "emailNotifications": true}` | identical |
| pref-12 | `GET /api/preferences/u2` | 200 application/json `{"userId": "u2", "theme": "dark", "locale": "de-DE", "emailNotifications": true}` | 200 application/json `{"userId": "u2", "theme": "dark", "locale": "de-DE", "emailNotifications": true}` | identical |
| pref-13 | `POST /api/preferences/u1` | 405 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 405, "error": "Met...` | 405 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 405, "error": "Met...` | identical |
| pref-14 | `DELETE /api/preferences/u1` | 405 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 405, "error": "Met...` | 405 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 405, "error": "Met...` | identical |
| pref-15 | `GET /api/preferences/` | 404 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 404, "error": "Not...` | 404 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 404, "error": "Not...` | identical |
| pref-16 | `GET /api/preferences/user%20with%20space` | 200 application/json `{"userId": "user with space", "theme": "light", "locale": "en-US", "emailNotifications"...` | 200 application/json `{"userId": "user with space", "theme": "light", "locale": "en-US", "emailNotifications"...` | identical |
| pref-17 | `GET /api/preferences/newuser` | 200 application/json `{"userId": "newuser", "theme": "light", "locale": "en-US", "emailNotifications": true}` | 200 application/json `{"userId": "newuser", "theme": "light", "locale": "en-US", "emailNotifications": true}` | identical |
| pref-18 | `GET /API/preferences/alice` | 404 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 404, "error": "Not...` | 404 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 404, "error": "Not...` | identical |
| pref-19 | `PUT /api/preferences/trailing` | 200 application/json `{"userId": "trailing", "theme": "dark", "locale": "de-DE", "emailNotifications": true}` | 200 application/json `{"userId": "trailing", "theme": "dark", "locale": "de-DE", "emailNotifications": true}` | identical |
| pref-20 | `GET /api/preferences/trailing` | 406 - (empty) | 406 - (empty) | identical |

<details><summary>common, announcements and feedback, case by case (served by legacy-portal)</summary>

### common

| case | request | before (monolith on `main`) | after (through the edge) | result |
|---|---|---|---|---|
| common-01 | `GET /health` | 200 application/json `{"status": "UP", "service": "legacy-portal", "banner": "OtterWorks Portal (on-prem) - c...` | 200 application/json `{"status": "UP", "service": "legacy-portal", "banner": "OtterWorks Portal (on-prem) - c...` | identical |
| common-02 | `GET /actuator/health` | 200 application/json `{"status": "UP", "groups": ["liveness", "readiness"]}` | 200 application/json `{"status": "UP", "groups": ["liveness", "readiness"]}` | identical |
| common-03 | `GET /actuator/health/liveness` | 200 application/json `{"status": "UP"}` | 200 application/json `{"status": "UP"}` | identical |
| common-04 | `GET /actuator/health/readiness` | 200 application/json `{"status": "UP"}` | 200 application/json `{"status": "UP"}` | identical |
| common-05 | `GET /actuator/info` | 200 application/json `{}` | 200 application/json `{}` | identical |
| common-06 | `GET /does-not-exist` | 404 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 404, "error": "Not...` | 404 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 404, "error": "Not...` | identical |
| common-07 | `GET /HEALTH` | 404 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 404, "error": "Not...` | 404 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 404, "error": "Not...` | identical |
| common-08 | `GET /Actuator/health` | 404 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 404, "error": "Not...` | 404 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 404, "error": "Not...` | identical |
| common-09 | `GET /health` | 406 - (empty) | 406 - (empty) | identical |
| common-10 | `GET /health` | 200 application/json `{"status": "UP", "service": "legacy-portal", "banner": "OtterWorks Portal (on-prem) - c...` | 200 application/json `{"status": "UP", "service": "legacy-portal", "banner": "OtterWorks Portal (on-prem) - c...` | identical |

### announcements

| case | request | before (monolith on `main`) | after (through the edge) | result |
|---|---|---|---|---|
| ann-01 | `GET /api/announcements` | 200 application/json `[]` | 200 application/json `[]` | identical |
| ann-02 | `GET /api/announcements?publishedOnly=false` | 200 application/json `[]` | 200 application/json `[]` | identical |
| ann-03 | `POST /api/announcements` | 201 application/json `{"id": 1, "title": "Release", "body": "v1 is out", "published": true, "createdAt": "<in...` | 201 application/json `{"id": 1, "title": "Release", "body": "v1 is out", "published": true, "createdAt": "<in...` | identical |
| ann-04 | `POST /api/announcements` | 201 application/json `{"id": 2, "title": "Draft", "body": "coming soon", "published": false, "createdAt": "<i...` | 201 application/json `{"id": 2, "title": "Draft", "body": "coming soon", "published": false, "createdAt": "<i...` | identical |
| ann-05 | `POST /api/announcements` | 201 application/json `{"id": 3, "title": "Second", "body": "another", "published": true, "createdAt": "<insta...` | 201 application/json `{"id": 3, "title": "Second", "body": "another", "published": true, "createdAt": "<insta...` | identical |
| ann-06 | `GET /api/announcements` | 200 application/json `[{"id": 3, "title": "Second", "body": "another", "published": true, "createdAt": "<inst...` | 200 application/json `[{"id": 3, "title": "Second", "body": "another", "published": true, "createdAt": "<inst...` | identical |
| ann-07 | `GET /api/announcements?publishedOnly=false` | 200 application/json `[{"id": 1, "title": "Release", "body": "v1 is out", "published": true, "createdAt": "<i...` | 200 application/json `[{"id": 1, "title": "Release", "body": "v1 is out", "published": true, "createdAt": "<i...` | identical |
| ann-08 | `GET /api/announcements/2` | 200 application/json `{"id": 2, "title": "Draft", "body": "coming soon", "published": false, "createdAt": "<i...` | 200 application/json `{"id": 2, "title": "Draft", "body": "coming soon", "published": false, "createdAt": "<i...` | identical |
| ann-09 | `GET /api/announcements/999` | 404 application/json `{"error": "Not Found", "message": "announcement 999 not found"}` | 404 application/json `{"error": "Not Found", "message": "announcement 999 not found"}` | identical |
| ann-10 | `GET /api/announcements/abc` | 400 application/json `{"error": "Bad Request", "message": "For input string: \"abc\""}` | 400 application/json `{"error": "Bad Request", "message": "For input string: \"abc\""}` | identical |
| ann-11 | `POST /api/announcements/2/publish` | 200 application/json `{"id": 2, "title": "Draft", "body": "coming soon", "published": true, "createdAt": "<in...` | 200 application/json `{"id": 2, "title": "Draft", "body": "coming soon", "published": true, "createdAt": "<in...` | identical |
| ann-12 | `POST /api/announcements/999/publish` | 404 application/json `{"error": "Not Found", "message": "announcement 999 not found"}` | 404 application/json `{"error": "Not Found", "message": "announcement 999 not found"}` | identical |
| ann-13 | `GET /api/announcements?publishedOnly=false` | 200 application/json `[{"id": 1, "title": "Release", "body": "v1 is out", "published": true, "createdAt": "<i...` | 200 application/json `[{"id": 1, "title": "Release", "body": "v1 is out", "published": true, "createdAt": "<i...` | identical |
| ann-14 | `GET /api/announcements` | 200 application/json `[{"id": 3, "title": "Second", "body": "another", "published": true, "createdAt": "<inst...` | 200 application/json `[{"id": 3, "title": "Second", "body": "another", "published": true, "createdAt": "<inst...` | identical |
| ann-15 | `POST /api/announcements` | 400 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 400, "error": "Bad...` | 400 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 400, "error": "Bad...` | identical |
| ann-16 | `POST /api/announcements` | 400 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 400, "error": "Bad...` | 400 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 400, "error": "Bad...` | identical |
| ann-17 | `POST /api/announcements` | 400 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 400, "error": "Bad...` | 400 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 400, "error": "Bad...` | identical |
| ann-18 | `POST /api/announcements` | 400 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 400, "error": "Bad...` | 400 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 400, "error": "Bad...` | identical |
| ann-19 | `POST /api/announcements` | 400 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 400, "error": "Bad...` | 400 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 400, "error": "Bad...` | identical |
| ann-20 | `POST /api/announcements` | 400 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 400, "error": "Bad...` | 400 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 400, "error": "Bad...` | identical |
| ann-21 | `POST /api/announcements` | 415 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 415, "error": "Uns...` | 415 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 415, "error": "Uns...` | identical |
| ann-22 | `DELETE /api/announcements/1` | 405 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 405, "error": "Met...` | 405 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 405, "error": "Met...` | identical |
| ann-23 | `PUT /api/announcements` | 405 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 405, "error": "Met...` | 405 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 405, "error": "Met...` | identical |
| ann-24 | `GET /api/announcements?publishedOnly=abc` | 400 application/json `{"error": "Bad Request", "message": "Invalid boolean value [abc]"}` | 400 application/json `{"error": "Bad Request", "message": "Invalid boolean value [abc]"}` | identical |
| ann-25 | `GET /api/announcements?publishedOnly=FALSE` | 200 application/json `[{"id": 1, "title": "Release", "body": "v1 is out", "published": true, "createdAt": "<i...` | 200 application/json `[{"id": 1, "title": "Release", "body": "v1 is out", "published": true, "createdAt": "<i...` | identical |
| ann-26 | `POST /api/announcements` | 201 application/json `{"id": 4, "title": "Coerced", "body": "string bool", "published": true, "createdAt": "<...` | 201 application/json `{"id": 4, "title": "Coerced", "body": "string bool", "published": true, "createdAt": "<...` | identical |
| ann-27 | `POST /api/announcements` | 201 application/json `{"id": 5, "title": "Extra", "body": "unknown field ignored", "published": false, "creat...` | 201 application/json `{"id": 5, "title": "Extra", "body": "unknown field ignored", "published": false, "creat...` | identical |
| ann-28 | `POST /api/announcements` | 400 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 400, "error": "Bad...` | 400 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 400, "error": "Bad...` | identical |
| ann-29 | `GET /api/announcements/` | 200 application/json `[{"id": 4, "title": "Coerced", "body": "string bool", "published": true, "createdAt": "...` | 200 application/json `[{"id": 4, "title": "Coerced", "body": "string bool", "published": true, "createdAt": "...` | identical |
| ann-30 | `GET /api/announcements/99999999999999999999` | 400 application/json `{"error": "Bad Request", "message": "For input string: \"99999999999999999999\""}` | 400 application/json `{"error": "Bad Request", "message": "For input string: \"99999999999999999999\""}` | identical |
| ann-31 | `GET /api/announcements?publishedOnly=false` | 200 application/json `[{"id": 1, "title": "Release", "body": "v1 is out", "published": true, "createdAt": "<i...` | 200 application/json `[{"id": 1, "title": "Release", "body": "v1 is out", "published": true, "createdAt": "<i...` | identical |
| ann-32 | `POST /api/announcements` | 201 application/json `{"id": 6, "title": "café", "body": "latin-1 body", "published": true, "createdAt": "<in...` | 201 application/json `{"id": 6, "title": "café", "body": "latin-1 body", "published": true, "createdAt": "<in...` | identical |
| ann-33 | `POST /api/announcements` | 201 application/json `{"id": 7, "title": "Trailing", "body": "tokens", "published": false, "createdAt": "<ins...` | 201 application/json `{"id": 7, "title": "Trailing", "body": "tokens", "published": false, "createdAt": "<ins...` | identical |
| ann-34 | `GET /api/announcements` | 406 - (empty) | 406 - (empty) | identical |
| ann-35 | `GET /api/announcements?publishedOnly=false` | 200 application/json `[{"id": 1, "title": "Release", "body": "v1 is out", "published": true, "createdAt": "<i...` | 200 application/json `[{"id": 1, "title": "Release", "body": "v1 is out", "published": true, "createdAt": "<i...` | identical |
| ann-36 | `GET /API/announcements` | 404 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 404, "error": "Not...` | 404 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 404, "error": "Not...` | identical |

### feedback

| case | request | before (monolith on `main`) | after (through the edge) | result |
|---|---|---|---|---|
| fb-01 | `GET /api/feedback/average-rating` | 200 application/json `{"averageRating": 0.0}` | 200 application/json `{"averageRating": 0.0}` | identical |
| fb-02 | `GET /api/feedback?userId=u1` | 200 application/json `[]` | 200 application/json `[]` | identical |
| fb-03 | `POST /api/feedback` | 201 application/json `{"id": 1, "userId": "u1", "rating": 5, "message": "great", "createdAt": "<instant:ISO_I...` | 201 application/json `{"id": 1, "userId": "u1", "rating": 5, "message": "great", "createdAt": "<instant:ISO_I...` | identical |
| fb-04 | `POST /api/feedback` | 201 application/json `{"id": 2, "userId": "u1", "rating": 3, "message": "ok", "createdAt": "<instant:ISO_INST...` | 201 application/json `{"id": 2, "userId": "u1", "rating": 3, "message": "ok", "createdAt": "<instant:ISO_INST...` | identical |
| fb-05 | `POST /api/feedback` | 201 application/json `{"id": 3, "userId": "u2", "rating": 1, "message": "bad", "createdAt": "<instant:ISO_INS...` | 201 application/json `{"id": 3, "userId": "u2", "rating": 1, "message": "bad", "createdAt": "<instant:ISO_INS...` | identical |
| fb-06 | `GET /api/feedback?userId=u1` | 200 application/json `[{"id": 2, "userId": "u1", "rating": 3, "message": "ok", "createdAt": "<instant:ISO_INS...` | 200 application/json `[{"id": 2, "userId": "u1", "rating": 3, "message": "ok", "createdAt": "<instant:ISO_INS...` | identical |
| fb-07 | `GET /api/feedback?userId=u2` | 200 application/json `[{"id": 3, "userId": "u2", "rating": 1, "message": "bad", "createdAt": "<instant:ISO_IN...` | 200 application/json `[{"id": 3, "userId": "u2", "rating": 1, "message": "bad", "createdAt": "<instant:ISO_IN...` | identical |
| fb-08 | `GET /api/feedback/average-rating` | 200 application/json `{"averageRating": 3.0}` | 200 application/json `{"averageRating": 3.0}` | identical |
| fb-09 | `POST /api/feedback` | 400 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 400, "error": "Bad...` | 400 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 400, "error": "Bad...` | identical |
| fb-10 | `POST /api/feedback` | 400 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 400, "error": "Bad...` | 400 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 400, "error": "Bad...` | identical |
| fb-11 | `POST /api/feedback` | 400 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 400, "error": "Bad...` | 400 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 400, "error": "Bad...` | identical |
| fb-12 | `POST /api/feedback` | 400 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 400, "error": "Bad...` | 400 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 400, "error": "Bad...` | identical |
| fb-13 | `POST /api/feedback` | 400 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 400, "error": "Bad...` | 400 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 400, "error": "Bad...` | identical |
| fb-14 | `POST /api/feedback` | 400 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 400, "error": "Bad...` | 400 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 400, "error": "Bad...` | identical |
| fb-15 | `GET /api/feedback` | 400 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 400, "error": "Bad...` | 400 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 400, "error": "Bad...` | identical |
| fb-16 | `GET /api/feedback?userId=` | 200 application/json `[]` | 200 application/json `[]` | identical |
| fb-17 | `POST /api/feedback` | 201 application/json `{"id": 4, "userId": "u3", "rating": 4, "message": "string rating", "createdAt": "<insta...` | 201 application/json `{"id": 4, "userId": "u3", "rating": 4, "message": "string rating", "createdAt": "<insta...` | identical |
| fb-18 | `POST /api/feedback` | 201 application/json `{"id": 5, "userId": "u3", "rating": 2, "message": "meh", "createdAt": "<instant:ISO_INS...` | 201 application/json `{"id": 5, "userId": "u3", "rating": 2, "message": "meh", "createdAt": "<instant:ISO_INS...` | identical |
| fb-19 | `POST /api/feedback` | 201 application/json `{"id": 6, "userId": "u3", "rating": 4, "message": "float rating", "createdAt": "<instan...` | 201 application/json `{"id": 6, "userId": "u3", "rating": 4, "message": "float rating", "createdAt": "<instan...` | identical |
| fb-20 | `GET /api/feedback/average-rating` | 200 application/json `{"averageRating": 3.1666666666666665}` | 200 application/json `{"averageRating": 3.1666666666666665}` | identical |
| fb-21 | `GET /api/feedback?userId=u3` | 200 application/json `[{"id": 6, "userId": "u3", "rating": 4, "message": "float rating", "createdAt": "<insta...` | 200 application/json `[{"id": 6, "userId": "u3", "rating": 4, "message": "float rating", "createdAt": "<insta...` | identical |
| fb-22 | `POST /api/feedback` | 400 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 400, "error": "Bad...` | 400 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 400, "error": "Bad...` | identical |
| fb-23 | `POST /api/feedback` | 415 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 415, "error": "Uns...` | 415 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 415, "error": "Uns...` | identical |
| fb-24 | `DELETE /api/feedback` | 405 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 405, "error": "Met...` | 405 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 405, "error": "Met...` | identical |
| fb-25 | `GET /api/feedback/average-rating?extra=1` | 200 application/json `{"averageRating": 3.1666666666666665}` | 200 application/json `{"averageRating": 3.1666666666666665}` | identical |
| fb-26 | `GET /api/Feedback?userId=alice` | 404 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 404, "error": "Not...` | 404 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 404, "error": "Not...` | identical |
| fb-27 | `GET /api/feedback/Average-Rating` | 404 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 404, "error": "Not...` | 404 application/json `{"timestamp": "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>", "status": 404, "error": "Not...` | identical |
| fb-28 | `POST /api/feedback` | 406 - (empty) | 406 - (empty) | identical |
| fb-29 | `GET /api/feedback?userId=xml-client` | 200 application/json `[{"id": 7, "userId": "xml-client", "rating": 5, "message": "saved before 406", "created...` | 200 application/json `[{"id": 7, "userId": "xml-client", "rating": 5, "message": "saved before 406", "created...` | identical |

</details>
