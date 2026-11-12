---
name: iri-policy-inquiry
description: >
  Reusable Oracle legacy-flat to IRI Policy Inquiry v1.1.5 mapping, lineage,
  frozen parity, schema validation and per-operation implementation ownership.
---

# IRI Policy Inquiry conversion

Work in `industries/insurance/iri-policy-inquiry/`. Read ESTATE.md,
legacy-api/src/main/java/app/synthetic/insurance/LegacyMapper.java and
JdbcInquiryRepository.java, and lineage/LINEAGE.md before changing an operation.
Pinned authority: vendor/iri-policy-inquiry-v1.1.5/PolicyInquiry_v1.1.5.yml.
Fixture DDL/seed: services/industry-solutions/insurance/db/annuity/.

## Running

From repo root:
```sh
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
pip3 install --user pyyaml jsonschema
make insurance-up NS=iri
make iri-legacy-up NS=iri
make iri-api-up NS=iri
make iri-api-test NS=iri
```

Never start/stop a database or API owned by another session. Legacy port is
18080 + crc32(NS)%1000; IRI port is 19080 + offset, Oracle is 51521 + offset.
Oracle FREEPDB1 schema/user/password defaults are ANNUITY_INQ/annuity_inq/annuity_inq
(synthetic fixture only; application.yml permits DB_URL/DB_USER/DB_PASSWORD).

## Rules and decisions

lineage/lineage.yaml is the machine-readable source of truth. Deliberately omitted
optional parents and their required children use omitted-optional, not sign-off;
they remain in per-operation tables and separate parity counts, never as passes.
The FUND_UNITS segment decision is one sign-off covering all required segment fields.
Change lineage.yaml, then
run `python3 lineage/render.py`; `--check` detects stale LINEAGE.md.
Do not maintain a second mapping table in parity tooling.

- YYYYMMDD dates become ISO YYYY-MM-DD; invalid dates fail, never coerce.
- Legacy numeric strings are unsigned, zero-padded, implied-decimal digits.
  Use LegacyMapper's scale, not the SQL display: values amounts 15 digits/2;
  fund allocation percent 5/2; units 18/6; unit price 15/6; fund value 15/2.
  Emit JSON numbers, not digit strings. Avoid binary floating-point transforms.
- RTN_CD 00/04/08/96 becomes HTTP 200/404/400/503. Non-success bodies conform
  to Error (required code/message, optional timestamp/validationErrors).
  Error.code has three dot-separated alphabetic tokens; correlationId is echoed
  in the header only, never the Error body. Shared advice already implements this.
- CNTR_NO validates the policyNumber request path, not an invented response field.
  Summary/funds are unpadded, values pads to 10; compare numerically.
- Summary status IF/LP/SR/TM maps ACTIVE/LAPSED/SURRENDERED/TERMINATED.
  PI -> PENDINGISSUED is inferred sign-off; DP has no spec enum (sign-off).
  QUAL_CD NQ/IRA/ROTH -> Non-Qualified/IRA/Roth IRA.
  PROD_NM -> product.planName; PLAN_CD -> product.planCode (FIXED/FLEX is
  not a product type); PROD_CD -> shortName is proposed sign-off.
  productType, issueType, policyLastRefreshDateTime have no legacy source;
  carrierId/carrierName are config constants with business values still sign-off.
  ISS_DT/MAT_DT belong to /dates; OWN_NM/ANN_NM to /parties.
  GRX_IND 0/1/3 is undocumented and stays on sign-off.
- Values: VAL_DT -> valuesAsOfDate, ACCT_VAL -> accountValues.endingAccountValue,
  SURR_VAL -> accountValues.surrenderValue, PREM_TD -> totalDepositITD.
  WDR_TD -> totalNetWithdrawalSinceIssue needs net-versus-gross sign-off.
  CASH_VAL/DTH_BEN/SURR_CHG have no PolicyValue element (sign-off).
  Omit optional withdrawalValues because its required child has no source.
- Repeated _NN groups become arrays, preserving ORDER BY fund_code. FUND_CNT
  -> totalItemsCount before paging and itemsCount after paging. startIndex is
  zero-based (default 0), limit defaults 50 and maxes at 200.
  FUND_CD/NM -> fundId/fundName, UNIT_VAL -> fundPrice, FUND_VAL -> totalFundValue.
  FUND_UNITS -> fundSegments[0].numberOfUnits is proposed sign-off; emitting
  a segment requires every other required segment field too (see lineage).
  ALLOC_PCT has no target. Required fundValuationDate is cross-table from
  POLICY_VALUES.VALUATION_DATE, absent from frozen funds (sign-off).
  Required fundAccountType has no source (sign-off).

**A difference is a failure until explained from data; business-only decisions
go on the sign-off list and the field stays in the payload.** Sign-off rows are
not passes and not permission to silently delete legacy data or invent a target
enum. Escalate an unresolved payload representation to the coordinating session;
schema checks may remain red until those decisions are made.
Live parity still requires a present, non-null target for each sourced sign-off
field (respecting array paging); missing targets fail rather than count as sign-off.
Dry-run sign-off handling is unchanged.

## Frozen evidence and checks

Capture owner alone runs `python3 parity/capture.py iri`.
parity/frozen/{summary,values,funds}/<contract>.json retains request/status,
rawSha256 and body; manifest.json describes all 300 records. Do not overwrite
or edit these to explain a failure.

From inquiry directory:
```sh
python3 lineage/render.py --check
python3 parity/compare.py --op summary --ns iri
python3 parity/schema_check.py --op summary --ns iri
python3 parity/compare.py --op summary --dry-run
python3 -m unittest discover -s parity -p 'test_*.py'
```
Repeat checks for values/funds; dry-run transforms without making HTTP requests
and is not live parity. Reports: parity/reports/<op>-parity.{json,md},
<op>-schema.{json,md}, or <op>-dry-run.{json,md}. Schema validation uses the
vendored OpenAPI 3.1 response schema with Draft 2020-12, local refs and format
checking, all frozen contracts plus a required 404 case.
Repo-root equivalents: make iri-lineage-check, iri-compare OP=summary NS=iri,
iri-schema OP=summary NS=iri.

## Legacy drift replay

Use `make iri-parity-replay NS=iri` (default NS iri) to re-fetch the legacy book
and all three operations against frozen evidence without modifying it. Reports
in parity/reports/drift-<timestamp>.json/.md compare HTTP status, raw SHA256 and
decoded body, with field-level diffs and manifest contract additions/removals.
Direct CLI: `python3 parity/replay.py --ns iri --frozen-dir /baseline/copy --out /report/stem`.
Use an alternate copy to simulate drift; never mutate canonical frozen.
Exit 0 means complete/no drift, 1 means drift or invalid response, 2 means a
transport failure including incomplete HTTP reads (or CLI usage error), and 3
means an invalid baseline (including empty manifests or missing/malformed records).
Baseline errors write reports without contacting the API; all partial/baseline-error
reports are marked incomplete.
Bring up the fixture/API only when authorized; leave another session's processes alone.

## Parallel ownership

iri-api is the shared Spring Boot 3/JDK17 scaffold; read its README.
Operation sessions create files exclusively in their own main/test package:
`app.synthetic.insurance.iri.summary`, `.values`, or `.funds`.
Own controller/repository/mapper/DTO/test files there; constructor-inject
JdbcTemplate. Component scanning finds them without shared edits.
Do not touch another operation, shared/, application class/config, pom.xml,
wrapper, lifecycle, Makefile, lineage, parity tooling or this skill. Request shared
changes centrally. No operation controllers exist in the initial scaffold.
