# Dealer Android app conventions

Owned by mobile-team.

- Keep dealer-api-client independent of Android; use JUnit and MockWebServer there.
- Keep UI state in ViewModels and render it with Compose. Use DealerClient for test doubles.
- Preserve the Identity API request and response contract across consumers.
- Platform.Shared changes, especially TokenSigner, must be validated against this
  consumer's sign-in tests and
  `dealer-api-client/src/test/resources/identity/signin-response.json`.
- Run `make test` and `make build` with ANDROID_HOME set and JDK 17 or 21.
- Run `make ui-test` with a connected API 35 emulator after navigation changes.
- Use synthetic fixture values and example hosts.
