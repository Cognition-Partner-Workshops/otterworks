---
name: legacy-api-to-iri
description: Convert legacy flat-field inquiry APIs to IRI schemas using explicit lineage, frozen parity cases, decimal-safe transforms and business sign-offs.
---

# Legacy API to IRI Policy Inquiry

## Repository map

Root `$R` is `industries/insurance/iri-policy-inquiry`.

- `legacy-api/`: read-only legacy Spring Boot API; do not modify `legacy-api/src`.
- `vendor/iri-policy-inquiry-v1.1.5/PolicyInquiry_v1.1.5.yml`: authoritative OpenAPI 3.1 specification; never edit vendor files.
- `lineage/lineage.yaml`: machine-readable source of mapping decisions and sign-offs.
- `lineage/render.py`: generates committed `lineage/LINEAGE.md`; use `--check` to verify synchronization.
- `parity/record.py`: records immutable `parity/frozen/` cases and source/file fingerprints.
- `parity/parity.py`: schema and lineage comparator; ignored reports in `parity/reports/`.
- `iri-api/`: Java 17 / Spring Boot 2.7.18 skeleton, shared errors, correlation filter and schema test helper.
- `iri_lifecycle.py`: per-namespace IRI process on port `19080 + crc32(NS) % 1000`; legacy uses `18080 + offset`.
- Oracle fixtures: `services/industry-solutions/insurance/db/annuity/{01_tables,02_seed}.sql`.

## Conversion checklist

1. Preserve the frozen legacy set. **Never re-record it in a conversion PR.** Review MANIFEST fingerprints before comparing. A baseline recording is a separate, explicit step.
2. For every DB/legacy field declare its IRI JSON pointer, legacy format, transform, status, reason and sign-off in lineage. Generate the human table from YAML, never maintain it separately.
3. Implement each operation in its own controller, repository and mapper (`SummaryController`, `ValuesController`, `FundsController`). Keep shared skeleton files stable when parallelizing operations.
4. Use the transform catalog below; do not improvise business semantics. Review all unresolved sign-offs, including unexplained GRX_IND (S-01) and withdrawn/net semantics (S-12).
5. Validate responses against the vendored component schema, including date/date-time formats, and run frozen parity. A SIGNOFF is not a PASS; a schema-invalid response always fails, even for sign-off cases.

## Transform catalog and invariants

- `identity`: string equality.
- `contract_number`: digits, including padded legacy CNTR_NO, canonicalize to decimal with no leading zeros. Compare with the canonical **request path**. IRI-01: values pads to ten digits; summary/funds do not. `PolicyNumbers` validates 1..30 digits and supported Java long range. Per changelog C-2, **never echo policyNumber in a response body**.
- `yyyymmdd_to_date`: validate a real calendar date and emit ISO date (`20260630` → `2026-06-30`). IRI-03.
- `implied_decimal(scale)`: integer digits shifted by the explicit scale. `000000000051250` at scale 2 means `512.50`. Use Python Decimal / Java BigDecimal, **never float or double**. Fund unit values use scale 6. IRI-03.
- `enum_map`: explicit code mapping only. Unmapped codes designated for business sign-off produce SIGNOFF with a schema-valid 422 Error (DP → `policy.status.unmapped`, S-02), not invented enum values. Undeclared unmapped codes fail.
- `count`: map FUND_CNT to itemsCount and totalItemsCount; startIndex is 0 without paging parameters. Match the emitted list length. Pagination must use the IRI envelope, not a bare array.
- `indexed_list`: fields suffixed `_01.._NN` map to `funds[i-1]`, retaining legacy order by fund_code; apply the declared item transform.
- `dropped`: no IRI home in this operation. Document why; never invent an element or overload an unrelated one. This includes fields belonging to out-of-scope dates/parties operations and GRX_IND pending S-01.
- `provisional`: IRI-required element without a legacy source. Configure under `iri.provisional.<operation>.*` in application.yml, with the sign-off id in a comment. Never silently default in mapper code. Check schema validity, not equality to a fabricated legacy value. Source-backed provisional mappings retain their declared transform checks.

Provisional sources/decisions: carrierId SYNANN (S-03), issueType GUARANTEED (S-04), response-time UTC refresh timestamp (S-05), productType FIXED→FIXED/FLEX→DEFERRED (S-06), PLAN_CODE rather than invalid PRODUCT_CODE for planCode (S-07), OTHER fundAccountType (S-13), policy_values.valuation_date for fundValuationDate (S-14).

## Errors and correlation

| Legacy RTN_CD | HTTP | Error.code |
| --- | --- | --- |
| 00 | 200 | — |
| 04 | 404 | policy.inquiry.notFound |
| 08 | 400 | policy.inquiry.invalidPolicyNumber |
| 96 | 503 | policy.inquiry.unavailable |

No fund rows means legacy 404, not a successful empty list. Error bodies contain code, message and optional UTC timestamp; codes have three dot-separated alphabetic tokens. Echo the `correlationId` request header in the response, generating a UUID when absent, including error responses.

## Commands

Python dependencies: `pip3 install --user pyyaml jsonschema` (Python 3).

Java defaults to 11 on this machine; use JDK 17:

```bash
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export PATH="$JAVA_HOME/bin:$PATH"
make insurance-up NS=iri
make iri-legacy-up NS=iri
# Baseline creation only, never in a conversion PR:
make iri-legacy-record NS=iri
make iri-api-up NS=iri
make iri-parity NS=iri OP=summary
make iri-parity NS=iri OP=values
make iri-parity NS=iri OP=funds
make iri-parity-selftest
make iri-api-test
make iri-legacy-test
python3 industries/insurance/iri-policy-inquiry/lineage/render.py --check
make iri-api-down NS=iri
```

`IRI_URL` overrides the parity endpoint. The recorder supports `LEGACY_URL`, `OUT`, `FORCE=1`; direct scripts expose `--iri-url`, `--legacy-url`, `--out`, `--force`. For offline harness checks use `parity.py --frozen <temporary-copy> --reports <temporary-directory>`; never modify frozen fixtures to manufacture a result.

**Every commit message and PR title targeting `demo-iri-api` must contain `[skip ci]`: a push there deploys a tenant.** Do not commit reports, build output, runtime state or credentials.
