# Mobile claims (FNOL)

This is the screen adjusters use to file a first notice of loss from the Capacitor shell (`frontend/client-app`) instead of phoning it in. It only exists for insurance. It lives here and the shell wires it in at `/claims/fnol`, with a "Report a loss" link in the Desk menu.

## What it sends

`POST /api/v1/claims/fnol` with `Content-Type: application/xml`. The body is an ACORD `ClaimsSvcRq` / `ClaimsNotificationAddRq`, the shape the hub's receive port validates (`ACORD_ClaimsNotificationAddRq.xsd`) and `Fnol_to_CanonicalClaim` maps. `src/acord.ts` builds it:

| Screen | ACORD | Notes |
|---|---|---|
| Policy number | `Policy/PolicyNumber` | upper-cased, `POL-<LOB>-<n>` |
| Line of business | `Policy/LOBCd` | `AUTO` / `HOME`, filled from the policy prefix |
| Insured given name, surname | `InsuredOrPrincipal/GivenName`, `Surname` | |
| Tax id (optional) | `InsuredOrPrincipal/TaxId` | masked on the device with the hub's `PiiMaskingComponent.Mask(v, 4)` rule (`123-45-6789` -> `XXX-XX-6789`); left out when blank |
| Loss date | `ClaimsOccurrence/LossDt` | not in the future |
| Cause of loss | `LossCauseCd` | `COLL COMP GLAS THFT FIRE WATR WIND LIAB` only |
| Description | `IncidentDesc` | XML-escaped |
| Estimated loss | `EstimatedLossAmt` | string-normalised to two decimals |
| Injuries yes/no | `InjuryInd` | required, no default |
| City, state, postal code | `Addr/*` | |
| Photos | none | placeholder only; capture is not built yet |
| (device) | `RqUID`, `TransactionRequestDt`, `ReportedDt` | UUID and local clock |
| (device) | `ClaimNumber` | `CLM-<yyyy>-M<8 hex of RqUID>` |
| (device) | `Producer` | `AG-MOBILE` / `Thistlecombe field adjusters` |

The hub schema accepts some optional elements the screen does not capture: `EffectiveDt`, `PhoneNumber`, `EmailAddr`, `PriorFraudFlagInd`, `PoliceReportInd` and `AutoLossInfo` (VIN, driveable). The map leaves out phone, email and vehicle, and it defaults `PoliceReport` and `PriorFraudFlag` to `false`.

## Contract pin

`contract/` holds read-only copies of the hub's schema, map and 16-notice FNOL corpus with its canonical goldens (provenance is in `contract/SOURCE.md`). Two suites run with the shell's `npm test`. Both need `xmllint` and `xsltproc` and skip without them:

- `src/contract.test.ts` checks that every corpus notice validates against the schema and that `xsltproc` over the map reproduces the hub golden byte for byte. This proves the local stand-ins behave like the hub before any mobile code is trusted.
- `src/acord.test.ts` takes each corpus notice, enters it again through the mobile builder, validates the result and maps it. Every field the screen captures must equal the golden. `CLM-2026-100402` (`TOWG`) can't be entered because tow is not one of the eight causes.

## Run it

```bash
cd frontend/client-app
npm test && npm run lint && VITE_API_BASE_URL=http://localhost:8080/api/v1 npm run build
npx cap sync ios
node ../../industries/insurance/mobile-claims/tools/gateway-mock.mjs   # :8080, validates FNOL bodies against the vendored XSD
```

The mock (`tools/gateway-mock.mjs`, no dependencies) serves register, login, profile, documents, files, folders, search, settings, notifications and the FNOL endpoint. It returns `422 unmasked_tax_id` if a body carries a raw tax id and `400 schema_invalid` if `xmllint` rejects it. Received bodies go to `fnol-received/`, which git ignores.

## Open decisions

- Should `TOWG` be offered? The hub's `FastTrack` triage rule lists it and the corpus contains it. The screen offers the eight causes it was asked for.
- Police report and prior-fraud flag are not captured, so the hub defaults them to `false`. Across the corpus that changes 5 police-report values and 1 fraud flag from `true`.
- The claim number and producer id are minted on the device. The hub may want to assign them itself.
