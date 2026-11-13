# Platform.Shared

Subtree split name: `uc-vuln-shared-lib-platform-shared`

`Platform.Shared` is the NuGet library every service in the dealer, warranty and payments platform uses for outbound HTTP, file storage, token signing, password hashing and SQL query helpers. Its two consumers are the .NET API in `../dev-api` and the dealer portal BFF in `../dealer-portal`; the Android app in `../android-app` depends on the tokens it signs through the Identity API.

## Public API

The consumers compile against these entry points. Changing one of their signatures is a breaking change for both consumers.

| Type | Entry point | Used by |
|---|---|---|
| `Platform.Shared.Http.SafeHttp` | `Fetch(string url)` | Dealer image proxy, Payments webhook delivery, portal BFF |
| `Platform.Shared.Crypto.TokenSigner` | `Sign(string payload)`, `Verify(string payload, string signature)` | Identity tokens, Dealer export links, Payments webhooks, portal BFF session |
| `Platform.Shared.Storage.FileStore` | `Open(string root, string relativePath)` | Warranty attachments, Dealer exports |
| `Platform.Shared.Data.QueryHelpers` | `InClause`, `LikeContains`, `OrderBy`, `Page` | Dealer Dapper queries, Warranty reports |
| `Platform.Shared.Crypto` | `PasswordHasher`, `DataProtector`, `Base64Url` | Identity |

`tests/Platform.Shared.Tests/PublicApi.approved.txt` lists the full public surface and `PublicApiTests` fails when it drifts. Regenerate it with `UPDATE_PUBLIC_API=1 dotnet test` only when the change ships with a version bump and the consumer migration.

## Build and test

```bash
make test        # restore, build and run the xUnit suite
make pack        # pack Platform.Shared.<version>.nupkg into artifacts/feed
```

From the repository root, `make vsl-pack` does the same pack. The consumers' `nuget.config` files point at `industries/mfg/vuln-shared-lib/platform-shared/artifacts/feed`, so they restore without a token once the feed is populated.

## Packages

The `vsl-platform-shared` workflow builds, tests and packs on every pull request into `demo-vuln-shared-lib` that touches this directory. For ready (non-draft) pull requests from this repository it pushes the package to GitHub Packages (`https://nuget.pkg.github.com/Cognition-Partner-Workshops/index.json`) with `GITHUB_TOKEN`, skipping versions that already exist. Bump `<Version>` in `src/Platform.Shared/Platform.Shared.csproj` to publish a new version.

`azure-pipelines.yml` runs the same restore, build, test and pack steps on `ubuntu-latest`.
