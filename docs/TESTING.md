# Application testing

Use isolated unit and in-process integration tests while developing. Use the Compose tiers to
verify the behavior that mocks cannot cover: gateway routing and auth, persistence, search, and
other cross-service effects. Browser suites check the UI on top; a mocked browser test does not
verify its backend.

| Tier | CI behavior |
| --- | --- |
| Unit and service integration | Path-scoped jobs in `ci.yml`; nine suites also run on PRs and pushes to `main` in `test-coverage.yml`. |
| Provider contract | `integration-tests.yml` runs the Search OpenAPI suite against Search + MeiliSearch. No Pact, gateway-consumer or event compatibility gate yet. |
| PR smoke | Six auth, document and search API flows selected by `pytest -m smoke` against the minimal Compose stack. Unready gateway, no executed tests, and test failures fail the job. |
| Nightly full | All API tests are collected and run at 03:30 UTC, with the additional backend services. The golden admin-service is intentionally not started; failures on admin-dependent behavior remain visible. Degradation tests still require a separately controlled outage and opt-in. Manual runs accept a `full` input. |
| Browser E2E | `client-e2e.yml` runs landing plus a repeatedly run mocked margins test; run the broader Playwright or Cucumber suites locally. |

## Local commands

For a minimal backend smoke/contract run, execute from the repository root. The Compose
definitions use fixed container names and ports; use an idle local Docker daemon, not one
already running the development stack.

```sh
export COMPOSE_PROJECT_NAME=otterworks-testing
export COMPOSE_FILE=docker-compose.infra.yml:docker-compose.yml
docker compose up -d --build --wait --wait-timeout 180 \
  postgres redis localstack meilisearch api-gateway auth-service document-service search-service
curl -fsS localhost:8080/health
curl -fsS localhost:8087/health/ready
make test-smoke
uv run --with-requirements tests/contract/requirements.txt \
  python -m pytest tests/contract --junitxml=search-contract.xml
docker compose logs --no-color
docker compose down --volumes --remove-orphans
```

For full API, add `file-service collab-service notification-service analytics-service
audit-service report-service` to the Compose startup, then run
`API_FLOWS_REQUIRE_STACK=1 make test-api-flows`. Without strict mode, the API fixture skips if the
gateway cannot be reached. For browser testing in `frontend/client-app`, run `npm ci`,
`npx playwright install chromium`, then `npm run test:e2e` or `npm run test:bdd`. For live browser
scenarios, supply the running gateway via `API_GATEWAY_URL`; Playwright can also target an
existing frontend through `BASE_URL`.

## Test pyramid and baseline

Commands below are run in the service/app directory after installing its development
dependencies. Counts are approximate authored unit/integration cases unless marked as runtime
cases; cross-service tests are counted separately. A dash means no new workflow coverage floor.

| Component | Unit / integration evidence | Local command | Measured coverage → floor |
| --- | --- | --- | --- |
| API Gateway | 47 Go test functions; 71 runtime cases with subtests | `go test -race -cover ./...` | 59.47% statements → 58% |
| Auth | 16 unit, 13 Spring/H2 integration | Gradle 8.6: `gradle test jacocoTestReport` | 73.32% lines → 72% |
| Document | 21 unit, 55 in-process API/SQLite; 9 failing | `poetry run pytest --cov=app` | 80.93% statements → 79% (non-blocking) |
| Search | 17 unit, 24 Flask integration with mocked MeiliSearch; 18 separate live contract cases | `pytest --cov=app` | 75.42% statements → 74% |
| Collab | 35 unit, 10 Socket.IO integration; Redis adapter untested | `npm test` | 65.12% lines → 64%; Jest also enforces branch/function/statement floors |
| File | 9 unit, 2 Actix handler checks | `cargo llvm-cov --locked` | 15.21% lines → 14% |
| Client | 11 Vitest cases; 71 Playwright and 36 Cucumber scenarios separately | `npm test -- --coverage` | 6.30% lines → 6% |
| Workbench | 25 Vitest runtime cases | `npm test -- --coverage` | 93.04% lines → 92% |
| Admin dashboard | 82 Jasmine/Karma cases; 7 failing; 15 legacy Selenium scenarios separately | `npm test -- --code-coverage` with Chrome | 59.29% lines → 58% (non-blocking) |
| Admin service | 79 unit/model and 41 controller cases | `bundle exec rails db:schema:load && bundle exec rspec` against test Postgres | — (SimpleCov locally) |
| Analytics | 32 unit, 24 route/Testcontainers integration | `sbt test` with Docker | — |
| Audit | 53 runtime xUnit cases | `dotnet test tests/AuditService.Tests/AuditService.Tests.csproj` | — |
| Billing | 7 unit, 1 in-process API check | `uv run --locked pytest` | — |
| Notification | 33 Kotlin/JUnit cases | `gradle test` | — |
| Report | 51 unit, 36 Spring/MockMvc integration | `mvn test` with JDK 8 | — |
| Legacy portal | 3 unit, 13 Spring/JPA integration | `./mvnw test` | — |
| Legacy portal Lambdas | 24 announcements, 15 feedback, 14 preferences unit cases | `mvn test` in each module with JDK 21 | — |
| Legacy billing | No in-module suite; shared procedure parity | `make procs-up NS=dev && make procs-parity NS=dev` from root | — |
| Industry insurance | 29 Oracle SQL assertion call sites | `make insurance-up NS=dev && make insurance-test NS=dev` from root | — |
| Desktop and mobile shells | Electron six smoke checks; Android two starter examples; no iOS/WPF suite | Build web client, then `npm --prefix desktop test` | — |

## Coverage policy and known gaps

- The workflow publishes native profiles (Go), Cobertura (pytest and Rust), LCOV (Jest/Vitest)
  and JaCoCo (Java), plus JUnit where supported. Each job reports its outcome, and a final job
  aggregates coverage in the GitHub Actions summary. Missing or empty reports do not pass.
- Floors in [coverage-floors.json](../tests/coverage-floors.json) are just below measured
  baselines. Increase floors after sustained improvements; do not lower them to accommodate a
  regression. If instrumentation changes, remeasure and explain the change in the PR. The
  native Jest line threshold should match the central Collab floor. Coverage is not a proxy
  for test depth or comparable across different metrics.
- The document suite's unauthenticated fixtures reach endpoints expecting auth and get 401s;
  the restore test then reads a result of the wrong shape. This looks like fixture drift,
  not a documented planted bug. The coverage job is explicitly non-blocking and retains its
  failing JUnit report. Admin dashboard failures include unfinished fakeAsync timers, incorrect
  loaded-state expectations and a stale mock-token assertion. Its coverage job is also
  explicitly non-blocking and retains its failing JUnit report.
- The live Search document and file index endpoints return HTML HTTP 400 responses for empty
  bodies, but OpenAPI specifies JSON. Only those two cases are marked as strict expected failures:
  if either passes, CI fails until its marker is removed. No runtime behavior was changed.
- Prioritize broader real-dependency tests, event/API contracts, browser coverage beyond the
  current smoke, and baseline visibility for the remaining service suites.
