---
name: shared-library-consumers
description: >
  Who consumes Platform.Shared (industries/mfg/vuln-shared-lib/platform-shared) and how
  to prove a library change leaves them working. Covers the two NuGet consumers (dev-api
  and the dealer-portal BFF), the Android app that pins the Identity token, the
  repository-local feed filled by make vsl-pack, every SafeHttp.Fetch and TokenSigner
  call site, and the commands that run each consumer's tests.
---

# Platform.Shared consumers

`Platform.Shared` is the NuGet library in `industries/mfg/vuln-shared-lib/platform-shared`
(owner: platform-team). It is published to GitHub Packages from this repository, but
consumers build against the **repository-local feed** so a library change on a branch is
what they compile:

```bash
make vsl-pack    # packs platform-shared into platform-shared/artifacts/feed (no token needed)
```

Each consumer's `nuget.config` maps `Platform.Shared` to that feed only
(`packageSourceMapping`; nuget.org hosts an unrelated package with the same id) and uses
a project-local package cache that `make test` wipes, so a repack under the same version
is picked up. CI runs a second job that restores the published package from GitHub
Packages.

## Consumers and their tests

| Consumer | Path | Owner teams | Command (repo root) |
|---|---|---|---|
| .NET API (Dealer, Warranty, Payments, Identity) | `dev-api/` | dealer, warranty, payments, identity | `make vsl-dev-api-test` |
| Dealer portal BFF (+ Angular unit tests) | `dealer-portal/` | portal | `make vsl-pack vsl-dealer-portal-test` |
| Android app sign-in (Identity token pin) | `android-app/` | mobile | `make vsl-android-app-test` |

Library tests: `make -C industries/mfg/vuln-shared-lib/platform-shared test`. The public
surface is pinned by `PublicApiTests` against `PublicApi.approved.txt`.

## Call sites (paths under `industries/mfg/vuln-shared-lib/`)

`SafeHttp.Fetch(string url)`
- `dev-api/src/Dealer/Services/PriceBulletinService.cs` (POST /api/dealer/bulletins/refresh)
- `dev-api/src/Payments/Services/RemittanceStatementClient.cs` (POST /api/payments/remittance/pull)
- `dealer-portal/bff/src/DealerPortal.Bff/Notices/NoticeFeedService.cs`

`TokenSigner.Sign(string payload)` / `Verify`
- `dev-api/src/Dealer/Services/ExportLinkSigner.cs` (export download links)
- `dev-api/src/Payments/Services/WebhookSigner.cs` (webhook payloads)
- `dev-api/src/Identity/Services/AccessTokenService.cs` (access tokens)
- `dealer-portal/bff/src/DealerPortal.Bff/Session/PortalSessionService.cs` (portal session)
- Test token helpers: `dev-api/tests/{Dealer,Warranty,Payments}.Tests/TestTokens.cs`

Find any new ones before changing a signature:

```bash
git grep -nE 'SafeHttp\.Fetch|TokenSigner\.(Sign|Verify)' -- industries/mfg/vuln-shared-lib ':!*/platform-shared/*'
```

## The Identity token contract

Identity issues `v1.<base64url(payload JSON)>.<TokenSigner.Sign(base64url payload)>`. Three
places pin the exact token for the fixed synthetic user `dealer-ops@dealer.example`:

- `dev-api/tests/Identity.Tests/IdentityEndpointsTests.cs`
- `dealer-portal/e2e/stub-upstream.mjs` and `dealer-portal/bff/tests/DealerPortal.Bff.Tests/StubUpstream.cs`
- `android-app/dealer-api-client/src/test/resources/identity/signin-response.json` and `DealerRepositoryTest.kt`

Changing how `TokenSigner` signs changes that token: update every pin in the same change
and run the Android sign-in tests, not only the .NET suites.

## Changing the public API

1. Add the new signature; keep the old one as an `[Obsolete]` overload that still works.
2. Bump `<Version>` in `src/Platform.Shared/Platform.Shared.csproj` and regenerate
   `PublicApi.approved.txt` with `UPDATE_PUBLIC_API=1`.
3. Move every call site above to the new signature in the same branch, then run all three
   consumer commands after `make vsl-pack`.
4. A change that builds in the library but breaks a consumer shows up as a red
   `local-feed` / `bff (local Platform.Shared feed)` job in that consumer's workflow.
