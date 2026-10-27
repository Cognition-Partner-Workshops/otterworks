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

Rule coverage example:
`python3 ../scripts/rule_coverage.py --junit uk=target/surefire-reports-uk --junit de=target/surefire-reports-de --vitest ../frontend/fleet/reports/vitest-junit.xml`.
