# Fleet service

`src/main/java/com/otterworks/fleet` contains the API, profile configuration, and
domain model. Ticket-owned contexts are `eligibility` (GF02-GF04, GF33),
`assignment` (GF05-GF13, GF34), `returns` (GF14-GF18), `mileage` (GF19-GF25),
and `benefit` (GF26-GF31); each context can add files within its own package.

Country values are bound from `application-uk.yml` or `application-de.yml`.
To add a profile value, update the discovery catalog, the profile YAML, and
`CountryProfile`; `GF01_countryParametersComeFromProfile` fails until the bound
value matches the catalog. Country-specific decisions belong in profiles, not
conditionals.

Flyway migration ranges are domain 1.x, eligibility 10.x, assignment 20.x,
returns 30.x, mileage 40.x, and benefit 50.x. Run both profiles with
`./mvnw verify -Puk` and `./mvnw verify -Pde`; reports are kept in
profile-specific target directories.
`verify` also boots the packaged jar against embedded Postgres in that profile
(`PackagedJarBootIT`) and asserts `/v3/api-docs` and `/api/v1/profile` answer
200; the boot log is at `target/boot-<profile>.log`.

Rule coverage example:
`python3 ../scripts/rule_coverage.py --junit uk=target/surefire-reports-uk --junit de=target/surefire-reports-de --vitest ../frontend/fleet/reports/vitest-junit.xml`.

Assignment APIs include `GET /api/v1/assignments/pool` and
`GET /api/v1/assignments/vehicle-rules`, resumable drafts under
`/api/v1/car-requests/drafts/{employeeNo}` (including `POST .../submit`),
`GET /api/v1/employees/{employeeNo}/car`, and the cutover double-holder report
and confirmation endpoints under `/api/v1/assignments/cutover/double-holders`.
Assignment start-date validation uses the `OpenPeriodLookup` seam; until the
benefit-period implementation supplies a bean, calendar months from the current
month onward are open. Set `fleet.assignment.legacy-assignment-unload` to the
optional fixed-width `ASSIGNMENT.dat` path to include legacy double holders in
the cutover report.

Mileage APIs include `GET /api/v1/mileage/quote`, `POST /api/v1/mileage/claims`,
`GET /api/v1/mileage/claims/pending`, approval and rejection under
`/api/v1/mileage/claims/{id}`, employee claim history at
`/api/v1/mileage/employees/{employeeNo}/claims`, and reimbursement summaries at
`/api/v1/mileage/employees/{employeeNo}/reimbursement?period=YYYYMM`. Claims
freeze their profile rate and rounded amount when submitted; only approved
claims are included in reimbursement totals.

Mileage persistence changes are in `db/migration/mileage/V40_0__mileage_claim.sql`.

The frontend at `../frontend/fleet` has one route folder per context under
`src/routes/<context>/`. Its handwritten `src/api/client.ts` mirrors the API
contract in `/v3/api-docs`. From `frontend/fleet`, run
`npm ci && npm run build && npm test`; Vitest writes
`reports/vitest-junit.xml`, which feeds the rule coverage script.
