# Identity

Owned by identity-team.

Use Platform.Shared PasswordHasher, DataProtector and TokenSigner for cryptography. Preserve the ordered access-token payload and exact sign-in token contract; the integration test pins it.

Run `make test` from dev-api or `dotnet test tests/Identity.Tests`. Platform.Shared changes must be validated against this consumer: make vsl-pack at repo root then make test here.
