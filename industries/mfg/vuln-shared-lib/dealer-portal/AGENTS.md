# AGENTS.md: dealer-portal

Owned by `portal-team`. Angular 17 dealer portal (`src/`) with a .NET 8 BFF (`bff/`) that consumes `Platform.Shared` from `../platform-shared`.

## Conventions

- Angular: standalone components only, one folder per screen under `src/app/pages/`, HTTP calls only through `PortalApiService` and `AuthService` in `src/app/core/services/`. Specs sit next to the file they test.
- All browser traffic goes to the BFF under `/bff`; the browser never calls the dealer platform API directly and never sees the bearer token.
- BFF: minimal API endpoints in `bff/src/DealerPortal.Bff/Endpoints/`, upstream calls only through `Upstream/DevApiClient.cs`.
- Keep every `Platform.Shared` call in the service classes that already own it: `SafeHttp.Fetch` in `Notices/NoticeFeedService.cs`, `TokenSigner` in `Session/PortalSessionService.cs`.
- Fixture keys, users and hosts are synthetic (`vsl-synthetic-*`, `*.example`). Never add a real credential or a real customer name.

## Commands

```bash
make vsl-pack        # repository root, once per library change
make test            # npm ci, Karma (ChromeHeadless), dotnet restore/build/test of bff/
make build           # production Angular build and BFF build
make e2e             # Playwright smoke suite (BFF + stub upstream on ports 5080/5199)
```

Karma needs Chrome; set `CHROME_BIN` if it is not on the default path. The BFF restores through `bff/nuget.config` (nuget.org plus the local feed `../../platform-shared/artifacts/feed`) into the project-local cache `.nuget/packages`, which `make test` wipes so the freshly packed library is what gets compiled.

## Platform.Shared changes

This project is a consumer of `Platform.Shared`. Any change to `../platform-shared` must be validated here before it merges: run `make vsl-pack` at the repository root, then `make test` and `make e2e` in this directory. The `vsl-dealer-portal` workflow runs on library changes for the same reason; its local-feed job is the one that fails when the library breaks this consumer.
