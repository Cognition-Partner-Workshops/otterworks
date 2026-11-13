# Dealer platform API

Subtree split name: `uc-vuln-shared-lib-dev-api`

Dealer inventory and Identity account services targeting .NET 8. Build the local Platform.Shared feed with `make vsl-pack` at the repository root, then run `make test` here. Dealer uses SQLite and Dapper; Identity uses SQLite and EF Core. Runtime databases and exports are stored under data/. Identity accounts are provisioned by the account administration process.
