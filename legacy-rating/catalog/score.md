# Golden catalog score

Baseline `1b421600`; run `INSR_20261124`.

| Metric | Count | Definition |
| --- | ---: | --- |
| Found | 105 | Distinct rule entries in [rules.md](rules.md). |
| Proven | 24 | Executed evidence in both legacy stacks distinguishes the condition. |
| From-table | 49 | Executed, distinguishing table-backed rule. Kept separate from Proven. |
| Amber | 11 | Unresolved legacy behavior: minimum timing, quote-only charges or the latent wind step. |
| Unproven | 21 | Source- or table-backed but not distinguished by the golden outputs. |
| Missed | 0 | No unmatched data rows or known omitted rating conditions after source and table cross-check; this is not a claim of complete fixture coverage. |

The four status counts sum to Found. Amber is a rule count, not a fixture mismatch count.

## Table reconciliation

| File | Data rows | Dedicated rules | Row coverage limits |
| --- | ---: | --- | --- |
| `class-factors.dat` | 15 | R47–R60, R105 | 11 rows have distinguishing evidence. GL/91111 and PR/0567 are blocked by eligibility (P0000005/P0000009); WC/8810 is blocked by line validation (P0000013); the 2027 GL/18501 row has no in-force fixture. |
| `line-eligibility.dat` | 4 | R61–R64 | CA/7911 selects a Y row by its input key (P0000042); output alone cannot distinguish the explicit Y from no row. |
| `territory-factors.dat` | 13 | R65–R77 | PR/060 only ran as expired and fell back (P0000023); its in-force window ends before any current PR class rate starts. There is no PR/WND row, not an unused row. |
| `minimum-premium.dat` | 6 | R78–R83 | WC minimum is blocked by line validation (P0000013). |
| `overrides.dat` | 3 | R84–R86 | All three replacement rows are distinguished by output (P0000031/P0000035/P0000037). |

All 41 current data rows are accounted for. Of these, 34 have distinguishing execution evidence, five are unreachable with the current tables/gates, one explicit allowance row is selected but not observably different from no match, and one (R105) is reachable by date but not exercised by the golden fixtures. R51's existing `from-table` count reflects the demonstrated 2026 rate only; its date contradiction is recorded in [rules.md](rules.md).

## PR #3396 batch refresh

`make insrules-reset` ran all three batches on the 200 golden policies at both base `aad408aa7` and head `c74073af3`. Each stack's outputs were byte-for-byte unchanged. The 2027 GL/18501 row remains unproven; the shifted citations do not change the witnesses, coverage limits or statuses of R18, R52–R60 or R74. See the [parity report](../parity/report.md) for the executed counts.

## Golden catalog baseline run

`make insrules-reset` rebuilt and ran the estate in 87 seconds. The script invokes the Java baseline as well; this catalog scores only legacy rules.

- Both legacy outputs contain exactly the 200 fixture IDs: 190 OK, 7 DEC (1 EX01, 1 EX02, 5 EX04), and 3 REJ (1 LN, 2 EX).
- COBOL vs Pharo with the repository driver’s keyed hashes and six shared rating fields: 195/200 matches; 5 differences, all R94. The launcher may return success despite parity mismatches; the pair totals, not the launcher exit status, are the evidence.
- Localhost Pharo quote screen: 200/200 fixture IDs matched the Pharo batch on all eight displayed fields. This is a separate HTTP replay, not a check performed by `parity/driver.py`. To reproduce it from the repository root with the default localhost port (8091):

  ```sh
  make insrules-reset
  python3 legacy-rating/catalog/replay_quote_screen.py
  ```

  The reset writes `legacy-rating/build/pharo.txt` and starts the quote screen. The replay sends one GET per record in `legacy-rating/fixtures/policies.dat`, parses the rendered quote table, and compares it with the corresponding batch record. It keeps the fixture ID outside the HTTP response because the screen uses the ID `SCREEN`.
- Pharo charges endorsements on 73/200 policies. COBOL has no endorsement field. With the corrected copybook position used only for this evidence, raw totals differ on 77/200 policies (72 endorsement alone, 4 order alone, 1 both). Those are separate from the shared-field mismatch metric.
- Output SHA-256, COBOL: `cf852a562fea6e4b31ff63a0602e4765f9bd8bedbfa65664aad20d46eea868ad`.
- Output SHA-256, Pharo: `adfad3afab8556a2b2307bf023dd8718a5da712107d42d7ffa96f34e327c8e96`.

## Parity reader defect (not changed here)

`parity/driver.py:46` reads the 11-character total at `r[56:67]`. `cobol/copybooks/RATEOUT.cpy:5–15` places the fee at `r[52:57]` and total at `r[57:68]`: the current reader includes the last fee digit and drops the total’s last digit/overpunch. For P0000001 the current slice decodes to $90.65, while the copybook slice decodes to $906.50 ($871.50 + $35.00).

Totals and fees are not among the six shared driver fields (`parity/driver.py:20–23,104–108`); this defect does not explain the five shared-field differences. The catalog used the copybook layout for fee and total evidence without changing the driver.

## Merge inputs

- COBOL extract at `a2de6efe`, 86 entries; Pharo extract at `eeb99b19`, 92 entries. These were cross-checked against the baseline programs, the five data files, and the executed golden outputs, not copied onto the catalog branch.
