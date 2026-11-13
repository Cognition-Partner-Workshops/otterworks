# Development conventions

Build files belong to platform-team. Dealer belongs to dealer-team; Identity belongs to identity-team. Use controller, model, repository and service folders. Keep JSON camelCase and test through WebApplicationFactory without external services. Use synthetic credentials and .example hosts only.

Run `make test` here. Platform.Shared changes must be validated against this consumer: make vsl-pack at repo root then make test here.
