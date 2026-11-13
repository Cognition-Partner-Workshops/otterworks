# Dealer Android app
Subtree split name: `uc-vuln-shared-lib-android-app`

Owned by mobile-team. Native Kotlin and Jetpack Compose dealer workspace.

## Modules and screens

- `dealer-api-client` is a Kotlin/JVM Retrofit client with DTOs, a TokenStore contract,
  request interceptors and a DealerRepository facade.
- `app` provides sign-in, inventory, claims and claim submission screens with ViewModels,
  loading states, empty states and retry actions. Navigation starts at sign-in each launch.

The app consumes Identity's token contract. It does NOT consume the Platform.Shared
NuGet package. Identity responses are pinned in
`dealer-api-client/src/test/resources/identity/signin-response.json`; coordinate token
contract changes with identity-team and platform-team.

## Local development

Use JDK 17 (JDK 21 can run Gradle too), Android SDK platform 35 and build-tools 35.0.0.
Set `ANDROID_HOME` to your SDK installation and accept SDK licenses with sdkmanager.
The Gradle 8.14.3 wrapper is checked in.

```sh
make test       # both modules' JVM tests; no emulator needed
make build      # debug and unsigned release APKs
make ui-test    # Compose sign-in smoke test on a connected API 35 emulator
make clean
```

The development API base URL is `http://10.0.2.2:5080/`, the emulator's host loopback.
Set the API_BASE_URL build field for a different local API.
Sign in with the synthetic dealer account `dealer-ops@dealer.example`.
The API expects dealer ID D-1001 for inventory and claims queries; the app uses the
dealer ID returned by sign-in. Requests include the mobile API key build field.

APKs are written to `app/build/outputs/apk/debug/app-debug.apk` and
`app/build/outputs/apk/release/app-release-unsigned.apk`. Release has no signingConfig.
The API client tests use MockWebServer and never require a running API.

## CI

GitHub Actions runs unit tests and both APK builds on estate pull requests that touch
this consumer, Platform.Shared or Identity. A separate emulator job runs the Compose
smoke test. APKs and test reports are uploaded as artifacts.
`azure-pipelines.yml` runs the same make targets with JDK 17 and an API 35 emulator.
