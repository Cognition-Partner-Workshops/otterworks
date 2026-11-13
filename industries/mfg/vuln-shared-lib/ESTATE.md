# Vulnerability remediation estate, shared library and consumers

This directory holds a dealer, warranty and payments platform for a vehicle manufacturer, seeded with 27 scanner findings across a shared library and its consumers. The estate lives only on the `demo-vuln-shared-lib` branch and resets to tag `seeded-v1` with `reset.sh`.

| Project | Directory | Owning teams |
|---|---|---|
| .NET 8 API with Dealer, Warranty, Payments and Identity | `dev-api/` | dealer-team, warranty-team, payments-team, identity-team |
| `Platform.Shared` NuGet library | `platform-shared/` | platform-team |
| Angular dealer portal with a BFF | `dealer-portal/` | portal-team |
| Kotlin and Compose dealer app | `android-app/` | mobile-team |

Each project builds and tests on its own, with its own `AGENTS.md`, GitHub Actions workflow and `azure-pipelines.yml`. The scanner export is three files under `dev-api/security/`: `findings.sarif`, `findings.csv` and `prioritized.csv`. The skill `.agents/skills/shared-library-consumers` lists the consumers of `Platform.Shared` and the commands that run their tests.
