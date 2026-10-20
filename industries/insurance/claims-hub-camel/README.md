# claims-hub-camel

Spring Boot 3.3 / Java 21 / Camel 4 replacement for the BizTalk claims hub in
[`../biztalk-claims-intake`](../biztalk-claims-intake/ESTATE.md).

## ClaimTriage rules

The BRE policy `ClaimTriage` 1.2 (`Rules/ClaimTriagePolicy.xml`) is kept as data in
[`src/main/resources/rules/claim-triage.csv`](src/main/resources/rules/claim-triage.csv): one row per
rule with `name`, `priority`, `condition`, `outcome` and `reason`. Thresholds and the fast-track cause
list are literals in the `condition` column and are read when the table loads; the Java code holds none
of them. The table to load is `claimshub.triage.rules-table` in `application.yml`.

Condition syntax: clauses joined by `and`, each `Fact op literal` (`==`, `!=`, `>`, `>=`, `<`, `<=`) or
`Fact in (A,B,C)`. Literals are `true`/`false`, a decimal (compared by value with `BigDecimal`), or a
single-quoted string. `Outcome` is the outcome set so far, empty before any rule sets one.

`TriageEvaluator` applies the agenda of `tools/triage_reference.py`: descending priority (file order within
a priority), each condition sees the outcome set so far, the first outcome set wins, every fired rule
appends its reason. `direct:claimTriage` takes a `TriageFacts` document and returns the `TriageResult`
with the outcome on the `TriageOutcome` header.

## Checks

```bash
(cd ../biztalk-claims-intake && python3 tools/triage_reference.py check)   # reference re-run, goldens current
./mvnw verify                                                               # parity, BRE name guard, unit tests
cat target/parity/triage-parity.md                                          # side-by-side report
```

- `TriageParityTest` runs the table over the 16 `corpus/golden/triage-facts` documents and compares rules
  fired, outcome and reasons with `corpus/golden/triage/*.json`; any difference fails the build.
- `RulesTableMatchesBreExportTest` fails when the table and the BRE export name different rules, or when a
  rule's priority, outcome or reason differs from the export.
