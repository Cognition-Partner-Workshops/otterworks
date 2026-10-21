# legacy-portal-dotnet

ASP.NET 9 port of the OtterWorks legacy portal (`services/legacy-portal`, Java 11 / Spring Boot 2.7).
It serves the same HTTP API with the same JSON: status codes, media types, key order, number formatting and
Spring's default error bodies. It reuses the Java service's PostgreSQL database layout, with one schema per
bounded context: `announcements`, `user_preferences` and `feedback`.

- Namespace root `OtterWorks.LegacyPortal`, assembly `LegacyPortal`
- Port **8098**. The Java service keeps 8095, so both can run side by side.
- Swagger UI: `/swagger/index.html`. Prometheus metrics: `/metrics`.

## Endpoints

| Area | Routes |
|---|---|
| Announcements | `GET /api/announcements[?publishedOnly=]`, `GET /api/announcements/{id}`, `POST /api/announcements`, `POST /api/announcements/{id}/publish` |
| User preferences | `GET /api/preferences/{userId}`, `PUT /api/preferences/{userId}` |
| Feedback | `POST /api/feedback`, `GET /api/feedback?userId=`, `GET /api/feedback/average-rating` |
| Common | `GET /health`, `GET /actuator/health`, `GET /actuator/health/liveness`, `GET /actuator/health/readiness`, `GET /actuator/info` |

`/health` returns `{"status":"UP","service":"legacy-portal","banner":"OtterWorks Portal (on-prem) - contact portal-support@otterworks.example"}`.
Readiness and aggregate health check the database. If PostgreSQL can't be reached, they return 503 with
`"status":"DOWN"`, as Spring Actuator does. Liveness stays `UP`.

## Running

```bash
# .NET service plus PostgreSQL 15 (initialized with services/legacy-portal/scripts/initdb.sql)
docker compose up -d --build
curl http://localhost:8098/health

# or on the host against an existing PostgreSQL
dotnet run --project LegacyPortal.csproj

# or without a database (EF Core InMemory)
DB_PROVIDER=InMemory dotnet run --project LegacyPortal.csproj
```

Docker image: `docker build -t legacy-portal-dotnet .`. It builds on the .NET 9 SDK, runs on `aspnet:9.0` as
non-root `appuser` (uid 1001), and has a `HEALTHCHECK` on `/health`.

## Tests

```bash
dotnet build LegacyPortal.csproj                               # warnings are errors
dotnet test Tests/LegacyPortal.Tests.csproj --filter "FullyQualifiedName~Unit"   # EF InMemory, no Docker
dotnet test Tests/LegacyPortal.Tests.csproj --filter "FullyQualifiedName~E2E"    # Testcontainers PostgreSQL 15, needs Docker
dotnet test Tests/LegacyPortal.Tests.csproj                    # everything
```

CI runs these steps in the `legacy-portal-dotnet` job of `.github/workflows/ci.yml` whenever
`services/legacy-portal-dotnet/**` changes.

## Configuration

Settings come from `appsettings.json`, which environment variables override.

| Variable / key | Default | Purpose |
|---|---|---|
| `DB_PROVIDER` / `Database:Provider` | `Postgres` | `Postgres` or `InMemory` |
| `DB_HOST` / `Database:Host` | `localhost` | PostgreSQL host |
| `DB_PORT` / `Database:Port` | `5432` | PostgreSQL port |
| `DB_NAME` / `Database:Name` | `legacyportal` | Database name |
| `DB_USER` / `Database:User` | `legacyportal` | Database user |
| `DB_PASSWORD` / `Database:Password` | `legacyportal` | Database password |
| `PORT` / `Server:Port` | `8098` | HTTP listen port |
| `Cors:AllowedOrigins` | `[]` | CORS origins. The Java service allows none. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | unset | OTLP traces and metrics are exported only when this is set |
| `Portal:SettingsFile` | `<app dir>/portal-settings.properties` | Branding properties file |

`portal-settings.properties` is copied unchanged from the Java service and ships next to `LegacyPortal.dll`.
`Configuration/PortalSettings.cs` loads it. It supports `${other.key}` references and the
`${base64Decoder:...}` lookup, and nothing else. Any other `${prefix:...}` lookup, such as script, dns, url or
env (the Commons Text "Text4Shell" family), stays as literal text and is never evaluated.

On startup, each context's `ISchemaInitializer` creates its schema and table if missing. It produces the same
DDL that Hibernate `ddl-auto=update` produces for the Java entities.

## Java to C# mapping

| Java (`com.otterworks.legacyportal`) | C# (`OtterWorks.LegacyPortal`) |
|---|---|
| `LegacyPortalApplication` + `application.yml` | `Program.cs`, `appsettings.json`, `Common/PortalModules.cs`, `Common/PersistenceExtensions.cs`, `Common/DatabaseSettings.cs` |
| `common.HealthController` | `Common/HealthController.cs` |
| Spring Boot Actuator (`/actuator/health`, liveness/readiness groups, `/actuator/info`) | `Common/ActuatorController.cs` + `Common/PortalDatabaseHealthCheck.cs` (readiness DB check) + `Common/CommonModule.cs` |
| `common.PortalBrandingSettings` + `portal-settings.properties` (Commons Text `StringSubstitutor`) | `Configuration/PortalSettings.cs` + `Configuration/PropertiesFormat.cs` + `portal-settings.properties` |
| `common.GlobalExceptionHandler` | `Common/PortalExceptions.cs` + `Common/PortalErrorMiddleware.cs` |
| Spring Boot default error body / Jackson | `Common/ErrorResponses.cs`, `Common/SpringJson.cs`, `Common/JsonConverters.cs` |
| Spring MVC request handling (case-sensitive paths, 406 on non-JSON `Accept`, any declared charset, trailing tokens ignored) | `Common/CaseSensitiveRoutingMiddleware.cs`, `Common/SpringJsonInputFormatter.cs`, `ReturnHttpNotAcceptable` in `Program.cs` |
| `Instant.now()` persisted to PostgreSQL | `Common/PortalClock.cs` |
| `announcements.Announcement` (JPA entity) | `Announcements/Models/Announcement.cs` (entity) + `Announcements/Models/AnnouncementResponse.cs` (DTO) + `Announcements/Data/AnnouncementsDbContext.cs` (mapping) + `Announcements/Data/AnnouncementsSchemaInitializer.cs` (DDL) |
| `announcements.AnnouncementController` (incl. `CreateAnnouncementRequest`) | `Announcements/Controllers/AnnouncementsController.cs` + `Announcements/Models/CreateAnnouncementRequest.cs` + `Announcements/Validation/CreateAnnouncementRequestValidator.cs`; Spring binding semantics in `Announcements/Binding/{SpringRequestBoolean,SpringPathLong,JavaText}.cs` and `Announcements/Controllers/MissingBodyWithoutContentTypeAttribute.cs` |
| `announcements.AnnouncementService` | `Announcements/Services/IAnnouncementService.cs` + `AnnouncementService.cs` |
| `announcements.AnnouncementRepository` | `Announcements/Data/IAnnouncementRepository.cs` + `AnnouncementRepository.cs` |
| `userpreferences.UserPreference` (entity) | `UserPreferences/Models/UserPreference.cs` + `UserPreferences/Data/UserPreferencesDbContext.cs` + `UserPreferences/Data/UserPreferencesSchemaInitializer.cs` |
| `userpreferences.UserPreferenceController` | `UserPreferences/Controllers/UserPreferencesController.cs` |
| `UserPreferenceController.UpdatePreferenceRequest` | `UserPreferences/Models/UpdatePreferenceRequest.cs` + `UserPreferences/Validation/UpdatePreferenceRequestValidator.cs` |
| `UserPreferenceController.PreferenceResponse` | `UserPreferences/Models/PreferenceResponse.cs` |
| `userpreferences.UserPreferenceService` | `UserPreferences/Services/IUserPreferenceService.cs` + `UserPreferenceService.cs` |
| `userpreferences.UserPreferenceRepository` | `UserPreferences/Data/IUserPreferenceRepository.cs` + `UserPreferenceRepository.cs` |
| `feedback.Feedback` (entity) | `Feedback/Models/FeedbackEntry.cs` + `Feedback/Data/FeedbackDbContext.cs` + `Feedback/Data/FeedbackSchemaInitializer.cs` |
| `feedback.FeedbackController` | `Feedback/Controllers/FeedbackController.cs` |
| `FeedbackController.{SubmitFeedbackRequest,FeedbackResponse,AverageRatingResponse}` | `Feedback/Models/FeedbackDtos.cs` + `Feedback/Validation/SubmitFeedbackRequestValidator.cs` |
| `feedback.FeedbackService` | `Feedback/Services/FeedbackService.cs` |
| `feedback.FeedbackRepository` | `Feedback/Data/FeedbackRepository.cs` |
| Spring component scan / bean wiring | `Announcements/AnnouncementsModule.cs`, `UserPreferences/UserPreferencesModule.cs`, `Feedback/FeedbackModule.cs`, `Common/CommonModule.cs` (`PortalModules` partials) |
| `AnnouncementServiceTest` | `Tests/Unit/Announcements/AnnouncementServiceJavaPortTests.cs` |
| `UserPreferenceServiceTest` | `Tests/Unit/UserPreferences/UserPreferenceServiceJavaPortTests.cs` |
| `FeedbackServiceTest` | `Tests/Unit/Feedback/FeedbackServiceJavaPortTests.cs` (+ PostgreSQL versions in `Tests/E2E/Feedback`) |
| `PortalBrandingSettingsTest` | `Tests/Unit/Common/PortalSettingsTests.cs` |
| `Dockerfile`, `docker-compose.onprem.yml` | `Dockerfile`, `docker-compose.yml` |

## Parity harness

`parity/requests.json` is an ordered corpus of 95 HTTP requests. `parity/run_parity.py` sends it to both
services and compares status, media type and JSON body, including key order and number formatting. Timestamps
are compared by format only. The run writes `parity/REPORT.md`.

```bash
# live Java (18095) vs live .NET (18098), each on its own fresh PostgreSQL 15
(cd ../legacy-portal && ./mvnw -B -DskipTests package)    # builds target/legacy-portal.jar for the Java container
docker compose -f parity/docker-compose.parity.yml down -v
docker compose -f parity/docker-compose.parity.yml up -d --build
python3 parity/run_parity.py --java http://localhost:18095 --dotnet http://localhost:18098

# without Java: compare against the captured Java oracle (needs a fresh .NET database)
python3 parity/run_parity.py --java-capture parity/java-reference.json --dotnet http://localhost:18098
```

Use `--context announcements|preferences|feedback|common` (repeatable) to run a subset.
