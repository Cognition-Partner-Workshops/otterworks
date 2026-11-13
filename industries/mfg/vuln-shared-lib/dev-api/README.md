# Dealer platform API

Subtree split name: `uc-vuln-shared-lib-dev-api`

Dealer inventory and Identity account services targeting .NET 8. Build the local Platform.Shared feed with `make vsl-pack` at the repository root, then run `make test` here. Dealer uses SQLite and Dapper; Identity uses SQLite and EF Core. Runtime databases and exports are stored under data/. Identity accounts are provisioned by the account administration process.

## Signing configuration

All four services fail startup without externally configured signing keys. Set
`Platform__Signing__CurrentKeyId`, `Platform__Signing__Keys__0__Id`, and
`Platform__Signing__Keys__0__Material` (base64 of at least 32 bytes) in the environment
for local runs. Use the same ring for Identity and its verifiers. For rotation, add
previous keys as `Keys__1__Id` and `Keys__1__Material`, keep them until old tokens
expire, then remove them. Never commit key material to appsettings files.

Outbound price bulletins use `Dealer:PriceBulletinAllowedHosts`; remittance pulls use
`Payments:Processor:RemittanceAllowedHosts`. Configure exact controlled host names,
with a port only when needed. URL and redirect policy errors retain the endpoints'
502 mapping. Missing or empty allowlists deny fetching.
