# Dealer portal

Subtree split name: `uc-vuln-shared-lib-dealer-portal`

The dealer portal is the browser front end dealers use to check their vehicle inventory, file and follow warranty claims and read OEM notices. It has two parts:

- an Angular 17 single-page app (standalone components, router, `HttpClient`) in `src/`, and
- a .NET 8 backend-for-frontend in `bff/` that serves the Angular build, holds the session cookie and proxies the dealer platform API (`../dev-api`).

Owned by `portal-team`.

## Screens

| Route | Screen | BFF calls |
|---|---|---|
| `/sign-in` | Sign-in | `POST /bff/session` |
| `/inventory` | Inventory list with search (`?q=`) | `GET /bff/inventory` |
| `/inventory/:vin` | Vehicle detail | `GET /bff/inventory/{vin}` |
| `/claims` | Warranty claims | `GET /bff/claims` |
| `/claims/new` | Submit a warranty claim | `POST /bff/claims` |
| `/notices` | Dealer notices from the OEM bulletin feed | `GET /bff/notices` |

## BFF

| BFF route | Upstream |
|---|---|
| `POST /bff/session` | `POST /api/identity/signin` |
| `GET /bff/inventory`, `GET /bff/inventory/{vin}` | `GET /api/dealer/inventory?dealerId=` |
| `GET /bff/claims`, `POST /bff/claims` | `GET/POST /api/warranty/claims` |
| `GET /bff/notices` | `Portal:NoticeFeedUrl` |

Configuration lives under `Portal` in `bff/src/DealerPortal.Bff/appsettings.json` and can be overridden with environment variables (`Portal__DevApiBaseUrl`, `Portal__NoticeFeedUrl`, `Portal__StaticRoot`, `Portal__ClientKey`, `Portal__SecureCookie`).

The BFF requires externally configured signing keys at startup. Set
`Platform__Signing__CurrentKeyId`, `Platform__Signing__Keys__0__Id`, and
`Platform__Signing__Keys__0__Material` (base64 of at least 32 bytes). Previous keys
can remain in `Keys__1` during rotation until old sessions expire. Missing or invalid
keys stop startup. Do not commit key material to appsettings files. Tests supply
synthetic keys through their host configuration.

`Portal:NoticeFeedAllowedHosts` supplies the explicit host allowlist for notice URLs
and redirects. Only allow controlled hosts; use `host:port` for nondefault ports.
The existing notice error response stays 502 for policy rejection.

The BFF uses `Platform.Shared`:

- `Notices/NoticeFeedService.cs` fetches the bulletin feed with `SafeHttp.Fetch`.
- `Session/PortalSessionService.cs` signs and verifies the `dp_session` cookie with `TokenSigner`.

## Build and test

```bash
make vsl-pack              # at the repository root: packs Platform.Shared into the local feed
make test                  # Karma unit tests + BFF xUnit tests (wipes the local NuGet cache first)
make build                 # production Angular build + BFF build
make e2e                   # Playwright smoke suite against the BFF and a stubbed upstream
```

From the repository root, `make vsl-dealer-portal-test` runs `make test` here.

For local development run the BFF (`dotnet run --project bff/src/DealerPortal.Bff`, port 5080) and `npm start`; the Angular dev server proxies `/bff` to the BFF.

## CI

`.github/workflows/vsl-dealer-portal.yml` runs on pull requests into `demo-vuln-shared-lib` that touch this directory or `platform-shared/`, and on manual dispatch. It runs the Angular build and unit tests on Node 20 and 22, the BFF tests against the freshly packed local feed, the BFF tests against `Platform.Shared` restored from GitHub Packages, and the Playwright smoke suite. `azure-pipelines.yml` runs the same steps on `ubuntu-latest`.
