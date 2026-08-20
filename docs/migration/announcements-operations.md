# Announcements — operator notes

Scope: `services/portal/announcements-service` only. Nothing here changes the contract, the
shared skeleton, or the compose profile.

## Running the container

```bash
make portal-up NS=dev PROFILE=announcements     # announcements-service + announcements-db
docker compose -f docker-compose.portal.yml -p otterworks-portal-dev ps
curl -s http://localhost:8101/health            # {"status":"UP","service":"announcements-service"}
make portal-down NS=dev                         # stops the stack and drops its volume
```

The image is a two-stage Temurin 21 build from the `./services/portal` context, runs as the
non-root `appuser` (uid 1001), and its healthcheck curls `/health` on 8101 — the same surface
compose polls. The published port is bound to `127.0.0.1`: the service carries no
authentication and is internal-only.

Schema and data:

- Flyway applies `V1__create_announcement.sql` into `announcements-db` on first boot
  (`Migrating schema "public" to version "1 - create announcement"`).
- A restart re-validates and does nothing (`Schema "public" is up to date. No migration
  necessary.`); `ddl-auto` stays `none`, so the container never mutates the schema.
- The datasource comes only from `SPRING_DATASOURCE_URL/USERNAME/PASSWORD` in the environment.
  The image carries no credentials and no baked datasource.
- `announcements-db` is the only database the service resolves; no other context's database is
  reachable from it.

## Two things the module build inside the image has to work around

Both are contained in `announcements-service/Dockerfile`; neither changes the module, the
parent POM, or the compose entry.

1. **Module builds go through each POM directly, not the parent reactor.** The build context is
   `./services/portal` but the image only copies `portal-common` and this context. A reactor
   build (`-pl … -am`) still requires *every* module named in the parent `<modules>` to exist
   in the context, so it fails once a second service is listed. The image instead installs the
   parent (`mvn -N install`), then `portal-common`, then packages this module with
   `mvn -f announcements-service/pom.xml`. Versions and plugin configuration still come from
   the parent through the child's `relativePath`.
2. **Maven Central rate limiting.** Some build hosts get HTTP 429 from Central, which fails the
   image build with no code change. Resolution is attempted against Central first; only if that
   fails does the build write a `settings.xml` mirroring Central to Google's read-only Central
   mirror and retry. A host that can reach Central never writes that file.
