---
name: iri-convert-one-operation
description: Convert one legacy annuity policy inquiry operation in otterworks into its IRI Policy Inquiry v1.1.5 Spring Boot endpoint, prove schema validity and parity against the frozen legacy set, and open one PR into demo-iri-api.
---

# Playbook: Convert one legacy inquiry operation to IRI v1.1.5

## Overview
The legacy annuity inquiry API (`industries/insurance/iri-policy-inquiry/legacy-api`, flat `/pinq/v1/<op>/{contractNo}` payloads over Oracle schema `ANNUITY_INQ`) is being replaced by IRI Policy Inquiry v1.1.5 endpoints in `industries/insurance/iri-policy-inquiry/iri-api`. Each run converts exactly ONE operation (summary, values or funds), following the repo skill `.agents/skills/legacy-api-to-iri/SKILL.md` and the lineage in `industries/insurance/iri-policy-inquiry/lineage/`, and proves it against the frozen legacy responses in `industries/insurance/iri-policy-inquiry/parity/frozen/`.

## What's Needed From User
- Repo: `Cognition-Partner-Workshops/otterworks`
- Operation: `summary` (getPolicySummary), `values` (getPolicyValue) or `funds` (getPolicyFunds)
- Base branch to start from (contains the frozen set, lineage, harness, skill and the iri-api skeleton), e.g. `devin/1794500574-iri-parity-baseline`
- PR target branch: `demo-iri-api`
- Whether to screen-record the parity runs

## Procedure
1. Check out the base branch and create `devin/$(date +%s)-iri-<op>` from it. Read the skill `.agents/skills/legacy-api-to-iri/SKILL.md`, `lineage/LINEAGE.md` (rows for your operation and the sign-off list) and your operation in `vendor/iri-policy-inquiry-v1.1.5/PolicyInquiry_v1.1.5.yml`.
2. Bring up the fixture: `make insurance-up NS=<ns>` (first pull of the Oracle image takes a few minutes). Use JDK 17 (`export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 PATH=$JAVA_HOME/bin:$PATH`); the default `java` may be 11.
3. Implement the endpoint in `iri-api` from the OpenAPI operation: one controller, repository and mapper for your operation in their own files, using only the skeleton's shared error handling, policy-number handling and correlationId filter. Apply exactly the lineage rules for your operation; emit provisional elements only from `iri.provisional.<op>.*` config, each commented with its sign-off id.
4. Add JUnit tests (no Oracle needed) that validate mapped responses, the 404/400/503 Error bodies and any 422 sign-off case against the vendored schema using the skeleton's schema-validation helper; run `make iri-api-test`.
5. Start the API (`make iri-api-up NS=<ns>`) and run parity: `make iri-parity NS=<ns> OP=<op>`. If recording was requested, start the screen recording and run parity in a visible terminal.
6. Fix every FAIL and schema-invalid case in the endpoint code. Never edit the frozen set, the vendored spec, the legacy API or another operation's lineage rows to get a pass. If a rule in the lineage itself is wrong or a new business question appears, leave the case failing or SIGNOFF and record it as a sign-off item instead of guessing.
7. Re-run `make iri-api-test` and the parity run until it is clean (0 FAIL, 0 schema-invalid); keep the final console output.
8. Stop what you started: `make iri-api-down NS=<ns>` and `make insurance-down NS=<ns>`.
9. Commit with `[skip ci]` in every commit message, push, and open ONE PR into `demo-iri-api` whose title contains `[skip ci]`. Body: what was built, the parity counts table (cases, PASS, FAIL, SIGNOFF, schema-invalid, provisional elements), the schema-validation result, the sign-off items touched, and how to reproduce.
10. Finish with a report: PR URL, parity counts, test results, sign-off items (existing ids and any new ones with the question for the business owner), deviations from the lineage, and the recording if one was made.

## Specifications
- One PR per operation into `demo-iri-api`, left open; title and every commit message contain `[skip ci]` (a push to a `demo-*` branch without it deploys a tenant).
- Every frozen case for the operation is exercised: 100 contracts + not-found, non-numeric and zero-padded cases.
- Parity: 0 FAIL, 0 schema-invalid; SIGNOFF cases are listed by contract with their sign-off id.
- All IRI 200 and error bodies validate against the vendored OpenAPI schema.
- Validation: the pasted `make iri-parity` and `make iri-api-test` outputs in the PR body.

## Advice and Pointers
- Contract numbers: canonical form has no leading zeros; legacy values pads to 10 digits (IRI-01). Do not echo policyNumber in bodies (spec changelog C-2).
- Amounts are implied-decimal strings; use BigDecimal and `movePointLeft(scale)`, never double. Dates YYYYMMDD -> ISO `format: date`.
- GRX_IND (IRI-04) and status DP (IRI-02) are sign-off items, not mapping problems to solve.
- Don't modify shared skeleton classes unless unavoidable; if you must, keep it minimal and call it out in the PR so sibling PRs can rebase.

## Forbidden Actions
- Do not re-record or edit `parity/frozen/`.
- Do not push to `demo-iri-api` directly, merge any PR, or omit `[skip ci]`.
- Do not invent values for IRI elements that have no legacy source outside the documented provisional config.
