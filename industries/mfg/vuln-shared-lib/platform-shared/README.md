# Platform.Shared

Subtree split name: `uc-vuln-shared-lib-platform-shared`

`Platform.Shared` is the NuGet library every service in the dealer, warranty and payments platform uses for outbound HTTP, file storage, token signing, password hashing and SQL query helpers. Its two consumers are the .NET API in `../dev-api` and the dealer portal BFF in `../dealer-portal`; the Android app in `../android-app` depends on the tokens it signs through the Identity API.

## Public API

The consumers compile against these entry points. Changing one of their signatures is a breaking change for both consumers.

| Type | Entry point | Used by |
|---|---|---|
| `Platform.Shared.Http.SafeHttp` | `Fetch(string url, IEnumerable<string> allowedHosts)` | Dealer image proxy, Payments webhook delivery, portal BFF |
| `Platform.Shared.Crypto.TokenSigner` | `Sign(string payload, ISigningKeyProvider keyProvider)`, `Verify(string payload, string signature, ISigningKeyProvider keyProvider)` | Identity tokens, Dealer export links, Payments webhooks, portal BFF session |
| `Platform.Shared.Storage.FileStore` | `Open(string root, string relativePath)` | Warranty attachments, Dealer exports |
| `Platform.Shared.Data.QueryHelpers` | `InClause`, `LikeContains`, `OrderBy`, `Page` | Dealer Dapper queries, Warranty reports |
| `Platform.Shared.Crypto` | `PasswordHasher`, `DataProtector`, `Base64Url` | Identity |

`tests/Platform.Shared.Tests/PublicApi.approved.txt` lists the full public surface and `PublicApiTests` fails when it drifts. Regenerate it with `UPDATE_PUBLIC_API=1 dotnet test` only when the change ships with a version bump and the consumer migration.

## Version 2 policies

Version 2.0.2 retains the 2.0 additions. Obsolete overloads honor default or environment
configuration, falling back to seeded 1.x behavior only when neither is set.
Versions 2.0.0 and 2.0.1 are already published and immutable.

`SafeHttp.Fetch(url, allowedHosts)` accepts only absolute HTTP or HTTPS URLs without
userinfo. Entries are exact host names or `host:port`, matched case-insensitively after
IDN/punycode normalization. A host-only entry permits only the scheme's default port.
There are no suffix or wildcard matches. Null or empty lists throw `ArgumentException`.
The transport disables automatic redirects. At most five redirects are followed, each
checked against the same allowlist, with HTTPS-to-HTTP downgrades rejected before sending.
Policy violations throw `SafeHttpPolicyException`, a subclass of `HttpRequestException`.
`FinalUri` is the last fetched URI. The existing response size bound remains in force.
The allowlist matches host names and does not pin resolved IP addresses; DNS rebinding of an allowlisted name is out of scope, so allowlist only hosts you control.

The obsolete `Fetch(url)` first uses `ConfigureDefaultAllowedHosts` configuration,
otherwise the comma-separated `PLATFORM_SHARED_FETCH_ALLOWED_HOSTS` environment variable.
Configured requests use the full explicit policy, including redirect checks. Entries
from the environment are trimmed; blank or malformed configuration throws and never
falls back to unrestricted fetching. A rejected default configuration remains denied
until replaced with a valid allowlist. Only when neither setting is present does it
perform unrestricted fetches with seeded redirect semantics, HTTP(S) validation,
response size bound and final URI. That no-config mode is unsafe for untrusted URLs.
Use the explicit overload.
For the explicit overload, one total timeout covers all redirects and body reads.
Reinstalling a used handler is supported. A previously started native handler that
still enables automatic redirects can be used by the legacy path, but the explicit
path rejects it before sending; supply a handler with automatic redirects disabled.

Create a `SigningKey` with an id and at least 32 bytes of externally managed material,
or use `SigningKey.FromBase64(id, text)` for base64 or base64url config binding. Never
commit production key material. `SigningKeyRing(currentKey, verificationKeys)` implements
`ISigningKeyProvider`: sign uses the current key, verify tries every verification key
with constant-time comparisons. Include the current key in the verification list.
To rotate, change the current key and keep the old key in the verification list until
old signatures expire, then remove it. Keys and the list are defensively copied.
HMAC-SHA256 signatures are unpadded base64url with no key id; the envelope stays
`v1.<payload>.<sig>`, but old SHA-1 signatures are not accepted.

The obsolete `Sign(payload)` and `Verify(payload, signature)` first use the provider
from `ConfigureDefaultKeyProvider`, otherwise `PLATFORM_SHARED_SIGNING_KEY` containing
base64 or base64url material of at least 32 bytes. Both configured paths use HMAC-SHA256
and reject seeded HMAC-SHA1 signatures. Malformed environment material throws instead
of using the seeded key. Only with neither setting present do they reproduce seeded
HMAC-SHA1 with the existing compiled synthetic fixture key, byte for byte. This public key is
not a secret and cannot authenticate real users or data. No new legacy key material
is introduced. The legacy path is retained only for the existing inert demo fixture,
not for production use; it has no runtime restriction to fixture payloads or hosts.
The obsolete overloads are deprecated for one release and will be removed in 3.0.0.
Migrate to explicit allowlists and providers for any real use.

`DeviceFingerprint.Compute(userAgent, deviceId)` is deterministic and unkeyed. It hashes
the UTF-8 prefix `Platform.Shared.DeviceFingerprint.v1` followed by a zero byte, then
each field as a 4-byte big-endian UTF-8 byte length followed by its bytes, using SHA-256.
The result is lowercase hex. Empty fields are supported, null fields throw
`ArgumentNullException`. It is an identifier, not an authentication secret.

The binary compatibility check builds a console consumer against a published-style
1.0.0 package made from the seeded commit, swaps only the library DLL, and runs it:

```bash
make compat
```

It runs the same compiled consumer first with the seeded DLL, then with the new DLL,
asserting the exact seeded signature and unrestricted fixture fetch behavior. It keeps
build artifacts under `artifacts/compat` and requires .NET 8 and git.

`make consumer-compat` runs the full unmigrated dev-api and BFF suites with their
1.0.0 pins, then swaps only the DLL in the test output and reruns both full suites
against the new DLL. This includes Dealer BulletinRefresh, Payments RemittancePull
and the old Identity SignInReturnsOrderedToken pin. Original DLLs are restored on exit.
The explicit-overload security tests remain separate in `make test`.

## Commands

```bash
make test        # restore, build and run the xUnit suite
make pack        # pack Platform.Shared.<version>.nupkg into artifacts/feed
```

From the repository root, `make vsl-pack` does the same pack. Both commands also build
seeded 1.0.0 directly from `seeded-v1` under ignored `artifacts/seeded` and put both
versions in the local feed. If the tag is absent, packing uses the locally available
pinned seeded commit before trying to fetch the tag. `make compat` also tests this
missing-tag fallback. The consumers' `nuget.config` files point at `industries/mfg/vuln-shared-lib/platform-shared/artifacts/feed`, so they restore without a token once the feed is populated.

## Packages

The `vsl-platform-shared` workflow builds, tests and packs on every pull request into `demo-vuln-shared-lib` that touches this directory. For ready (non-draft) pull requests from this repository it pushes the package to GitHub Packages (`https://nuget.pkg.github.com/Cognition-Partner-Workshops/index.json`) with `GITHUB_TOKEN`, skipping versions that already exist. Bump `<Version>` in `src/Platform.Shared/Platform.Shared.csproj` to publish a new version.

`azure-pipelines.yml` runs the same restore, build, test and pack steps on `ubuntu-latest`.
