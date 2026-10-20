# Thistlecombe Mutual agent desktop

The Thistlecombe Mutual skin of the shared WPF client in `clients/windows-desktop/OtterWorks.Desktop`
(.NET 8, `net8.0-windows`). Insurance-only code lives here; sign-in, registration, documents, the
gateway client, DPAPI session storage and `appsettings.json` come from the shared project by
`ProjectReference`, so upgrades to the shared client reach this desktop without a copy.

## Layout

| Path | What it is |
| --- | --- |
| `Thistlecombe.AgentDesktop/` | WinExe. `AgentShellWindow` wraps the shared `MainViewModel` and adds Policies / Claims / Documents navigation. |
| `Thistlecombe.AgentDesktop/Theme/Brand.xaml` | Name, colours (`#1D5C54` green, `#C08A2E` gold) and the mark, redrawn from `frontend/client-app/src/assets/thistlecombe-mark.svg`; re-declares the shared resource keys so the shared Documents screen picks up the skin. |
| `Thistlecombe.AgentDesktop/Theme/Ledger.xaml` | Grid, money cell and status pill styles for the two list screens. |
| `Thistlecombe.AgentDesktop/Services/CarrierMoney.cs` | The named rounding for premium and reserve (below). |
| `Thistlecombe.AgentDesktop.Tests/` | xUnit: rounding, fixture rows to the cent, request shape of `GET /policies` and `GET /claims`. |
| `stub/` | `policies.json`, `claims.json` and `build_fixtures.py`, which regenerates them. |

## Where the data comes from

| Screen | Columns | Source |
| --- | --- | --- |
| Policies | policy, product, holder, annual premium, status | `services/industry-solutions/insurance/db/oltp/02_seed.sql` on `demo-insurance`: `policies` joined to `products` on `product_code` (5 rows). |
| Claims | claim, policy, loss date, cause, reserve, status | `industries/insurance/biztalk-claims-intake/corpus` on `devin/1792473658-insurance-biztalk-fixture`, read with `git show` and never checked out (16 claims). Claim fields from `canonical/*.xml`; reserve is `ReserveEstimate` from `golden/*.triage-facts.xml`; status is `outcome` from `golden/*.triage.json`. |

Regenerate with `python stub/build_fixtures.py` from the repo root (needs the fixture branch fetched).
Money stays a decimal string in the JSON, exactly as the source wrote it.

## Rounding

Money is `decimal` at scale 2 and every column names its mode in `CarrierMoney`:

| Column | Source arithmetic | Mode | Constant |
| --- | --- | --- | --- |
| Annual premium | Oracle stores `annual_premium NUMBER(12,2)`; Oracle rounds half away from zero | HALF_UP | `PremiumRounding = MidpointRounding.AwayFromZero` |
| Reserve | BizTalk triage rule computes `ReserveEstimate` with .NET `Math.Round` | HALF_EVEN | `ReserveRounding = MidpointRounding.ToEven` |

Two corpus claims land on a tie and prove the reserve mode: CLM-2026-100405 (1002.50 x 1.25 = 1253.125,
golden 1253.12) and CLM-2026-100406 (2501.50 x 1.15 = 2876.725, golden 2876.72). HALF_UP would show
1253.13 and 2876.73. The seed premiums are already at scale 2, so the premium mode does not change any
displayed value today; it is named so a computed premium cannot silently pick up banker's rounding.

## Run it

```powershell
# terminal 1: the shared gateway stub with the insurance fixtures mounted
python clients/windows-desktop/stub/gateway_stub.py `
  --fixture /policies=industries/insurance/agent-desktop/stub/policies.json `
  --fixture /claims=industries/insurance/agent-desktop/stub/claims.json

# terminal 2
cd industries/insurance/agent-desktop
dotnet test Thistlecombe.AgentDesktop.sln -c Release
dotnet run --project Thistlecombe.AgentDesktop -c Release
```

The stub serves `/api/v1/auth/*`, `/api/v1/documents`, `/api/v1/files` and the two fixture routes on
`127.0.0.1:8080`; state is in memory and resets on restart.

## Known limits

- Policies and Claims are read-only lists; there is no search, paging or detail view.
- The Documents screen is the shared one. Its Files button fetches files but only shows a count
  (inherited from the shared client, see PR #2114).
- The real gateway has no `/policies` or `/claims` route yet; the stub is the only server for them.
