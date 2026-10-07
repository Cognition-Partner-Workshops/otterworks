# preferences-service

The user-preferences bounded context, extracted from the
[`legacy-portal`](../legacy-portal/README.md) modular monolith. Java 21, Spring Boot 3.3,
`jakarta.*`, its own PostgreSQL database (schema created by Flyway in
`src/main/resources/db/migration`). Nothing else reads or writes that database.

| Route | Behaviour (unchanged from legacy-portal) |
|---|---|
| `GET /api/preferences/{userId}` | stored preferences, or defaults `light` / `en-US` / `emailNotifications: true` |
| `PUT /api/preferences/{userId}` | `theme` and `locale` required, non-blank, max 20 chars; omitted `emailNotifications` is `false` |
| `GET /health` | `{"status":"UP","service":"preferences-service"}`; used by the image `HEALTHCHECK` and the chart probes |

## Strangler route

Clients keep calling the portal. The edge sends only `/api/preferences` and `/api/preferences/**`
to this service; everything else, announcements and feedback included, still goes to legacy-portal.

- Compose: [`docker-compose.portal.yml`](../../docker-compose.portal.yml) with the nginx edge in
  [`services/legacy-portal/strangler/nginx.conf`](../legacy-portal/strangler/nginx.conf). Every
  response carries `X-Served-By: legacy-portal` or `X-Served-By: preferences-service`.
- Kubernetes: [`infrastructure/helm/preferences-service`](../../infrastructure/helm/preferences-service)
  adds an Ingress for the `/api/preferences` prefix on the portal host. The chart's Service is
  ClusterIP and the chart refuses any other type.

```bash
docker compose -f docker-compose.portal.yml up --build --wait     # from the repo root
curl -i http://localhost:8095/api/preferences/alice
docker compose -f docker-compose.portal.yml down -v
```

## Build & test

```bash
cd services/preferences-service
./mvnw verify
```

## Parity

`parity/transcripts/monolith-main.json` is the HTTP transcript of the full legacy-portal corpus
(`services/legacy-portal/parity/requests.json`, 95 ordered cases) recorded with
`parity/record.py` against the monolith built from `main` before the extraction.
`parity/run.sh` brings the Compose stack up with empty databases and replays the corpus through
the edge with `services/legacy-portal/parity/replay.py`, comparing every case against that
transcript, then checks which upstream answered each module. CI runs it on every change. The
latest results are in [`parity/REPORT.md`](parity/REPORT.md).

```bash
services/preferences-service/parity/run.sh
```

## Cutover

The service starts with an empty database. Existing rows can be copied from the monolith's
`user_preferences.user_preference` table unchanged, because the table has the same shape:

```bash
pg_dump --data-only --table=user_preferences.user_preference "$LEGACY_PORTAL_DB_URL" \
  | psql "$PREFERENCES_DB_URL"
```
