---
name: commission-rule-extraction
description: Extract and reconcile Oracle compensation rules from packages, schema, triggers, warehouse ETL, and scanned specifications, with live characterization evidence and owner sign-off.
---

# Oracle business-rule extraction without behavior changes

## Start from a layout, not assumptions

1. Query DeepWiki for the named repository/fixture before reading SQL. Record index gaps and verify the requested branch locally. Do not infer that the README or main package contains all rules.
2. Read local agent guidance and check git status. Branch from the requested base. For OtterWorks insurance, base is `demo-insurance`; every commit must include `[skip ci]` to avoid tenant deployments. Never merge unless requested.
3. Inventory schema constraints/defaults, seed/config rows, package spec AND body, private functions/constants, row/statement triggers, ETL, views/materialized views, grants, startup orchestration, and existing tests. Follow the write path end to end. Treat fixture actors/policy examples as samples, not compensation policy.

## Read the paper independently

Render every scanned PDF page and visually read the actual images. Check tables, footnotes, dates, scope, and approval signatures. OCR is a navigation aid, not authority; the scan generator is not evidence that the scan says something. Record page/section citations and a complete clause-to-rule crosswalk, including requirements with no implementation. Flag unverifiable upstream mappings rather than asserting equivalence.

## Build an owner-readable ledger

Give each rule a stable ID, one plain business sentence, repository-relative source file with inclusive 1-based lines, scan match or explicit absence, green/amber classification, approval state, and executable test ID. Include code-only rules, exceptions, stored-data constraints, date operators, transaction effects, and reporting semantics. Separate business classification from test result: **amber PASS** means a discrepancy is faithfully characterized, not fixed or approved. Green is not approval either.

Reconcile independently: OLTP versus paper, warehouse versus paper, warehouse versus OLTP. Check values AND attributes: totals can reconcile while tier classifications differ. Never alter source PL/SQL to make the paper spec pass. Group ambiguous choices into a short owner sign-off list; leave reviewer/choice/date pending. For every tiered/piecewise rule provide a decision table with equality, below/above boundary, missing-history, and date-change cases. Keep observed configuration separate from proposed/spec configuration.

## Characterize against real Oracle

Use only a disposable local namespace. For insurance:

```sh
make insurance-up NS=rules
make insurance-test NS=rules
python3 services/industry-solutions/insurance/extraction/characterize.py \
  --namespace rules --allow-disposable-fixture --output /absolute/evidence/run
make insurance-down NS=rules
```

`cases.json` has ordered stateful cases; later DW tests consume earlier payment tests. Start fresh before rerunning. Run the existing regression suite BEFORE characterization to avoid its period-total assertions seeing deliberately stale facts created by the new cases. Fixture credentials in the harness are public local-only demo credentials, never production secrets.

Test exact arithmetic with Oracle NUMBER; compare emitted amounts/rows/error codes, not a Python reimplementation. Cover threshold equality, date equality and adjacent dates, month ends/anniversaries, cents and precision changes, cap interactions, reruns, rollback, paid-agent chargebacks, deleted splits, and changed source attributes. Require assertions to execute and SQL*Plus to exit successfully; fail on missing sentinels, unexpected codes, syntax failures, or catalog/test mismatches. Never turn unexpected behavior into a passing test without independently inspecting the source and documenting why it is a rule. State untested concurrency or upstream semantics explicitly.

Record the actual shell with `script --return --log-out ... --log-timing ... --command ...` (and a visible terminal recording when requested). Save SQL*Plus stdout, executed scripts, UTC time, Oracle version/image ID, source/spec/test SHA-256 fingerprints, and green/amber PASS/FAIL rows. Do not expose real secrets in echoed commands. Use fresh namespaces or explicit teardown between attempts; do not silently reuse contaminated test data.

## Deliver and clean up

For this fixture, `extraction/rules.json` is the catalog input; `render.py` validates ranges/coverage and generates Markdown, CSV, and sign-off. Keep `product-config.json` descriptive and pending approval; it must not silently become a deployed payment engine. `decision-tables.md` and `spec-crosswalk.md` preserve owner comparisons. Validate config references against catalog IDs and observed seed values. Run lint, Python compilation/type checks where available, and existing regressions; put raw evidence in attachments and the compact requested reports in the PR.

Stop Oracle with `make insurance-down NS=<owned namespace>` even on failure; it drops that namespace's volume. Verify no owned container remains, report cleanup explicitly, and do not affect other namespaces. Check git diff confirms package, trigger, seed, and ETL are unchanged. Open one PR into the requested branch, settle applicable checks, and leave it open.
