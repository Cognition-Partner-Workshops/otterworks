# Payments

Owned by payments-team.

Use EF Core for relational storage and FluentValidation for request validation.
Every security-relevant test carries [Trait("Category","Security")]. No new package without a note in the Package register.
Run `make test` from dev-api or `dotnet test tests/Payments.Tests`.
Platform.Shared changes must be validated against this consumer: make vsl-pack at repo root then make test here.

## Package register

- Platform.Shared: shared HTTP transport and event signatures.
- Microsoft.EntityFrameworkCore.Sqlite: settlement, refund and event storage.
- Newtonsoft.Json: settlement batch interchange.
- FluentValidation.DependencyInjectionExtensions: request validation registration.
- Microsoft.AspNetCore.Mvc.Testing (tests): endpoint host.
- Microsoft.NET.Test.Sdk (tests): test execution.
- xunit (tests): assertions and test cases.
- xunit.runner.visualstudio (tests): test discovery.
