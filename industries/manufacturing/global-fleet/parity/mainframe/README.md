# Mainframe holdout parity

There is no IDMS runtime in this sandbox, so `FLEBEN01` cannot run here. The twelve
committed holdout pairs `HP-202510` through `HP-202609` stand in for it. Their committed
`OUT` files are the only expected outputs. In particular, there is no expected output for
202610: that benefit period is open in `mainframe/unload/BENPRD.dat` and was never run.

`pairs.json` records each committed input and output path, checksum and record count, the
period row and BENRPT totals. It also reports, per input file, exact-row membership,
same-key differences and extra rows when compared with the current unload. These are
observations against the current unload, not an assumption that today's unload is a
historical snapshot from each run date. The consistency fields compare BENOUT record and
amount totals with the final BENRPT line and compare BENRPT detail rows with BENOUT rows.

```sh
python3 industries/manufacturing/global-fleet/parity/mainframe/build_pairs.py
python3 industries/manufacturing/global-fleet/parity/mainframe/decode.py \
  industries/manufacturing/global-fleet/mainframe/unload/BENOUT.dat
python3 industries/manufacturing/global-fleet/parity/mainframe/check_pairs.py
python3 industries/manufacturing/global-fleet/parity/mainframe/check_pairs.py \
  --candidate 'python3 industries/manufacturing/global-fleet/parity/mainframe/reference/fleben01.py --in {in} --out {out} --period {period}'
```

`decode.py` follows `mainframe/copybooks/LAYOUT.md`, including packed decimal and implied
decimal fields; `00000000` dates become JSON `null`. `check_pairs.py` verifies
`PAIRS.sha256`, the file metadata and internal report/output consistency. With
`--candidate`, it compares candidate `BENOUT.dat` and `BENRPT.txt` byte-for-byte with the
committed outputs and reports every mismatch as `failed`.

`reference/fleben01.py` is a straight calculation/output-format port of
`mainframe/batch/FLEBEN01.cbl`, using the settled behavior in `~/gf-work/FINDINGS.md`.
It is a self-test of the harness, not a replacement for IDMS or a source of expected
holdouts. Its byte-identical count and any first-difference diagnosis are reported below
after running all twelve pairs.

## Results

`check_pairs.py` verified all 84 manifest entries and all 84 `pairs.json` file entries.
Every one of the 12 pairs passed BENOUT/BENRPT consistency: BENOUT rows, BENRPT
`recordsWritten`, and BENRPT detail rows agree, as do taxable and reimbursement totals.
The reference port matched both committed output files byte-for-byte for all 12 periods
(12/12 BENOUT and 12/12 BENRPT); there was no differing record.

Every pair's five IN files are exact subsets of the current unload. No pair has
pair-only rows or same-key changed rows. The full current-only key lists are stored in
`pairs.json`; these are records now present in unload but absent from the historical
pair input. Input row counts by period are:

| Pair | ASSIGNMENT | BENPRD | EMPLOYEE | MILECLM | VEHICLE |
|---|---:|---:|---:|---:|---:|
| HP-202510 | 97 | 1 | 215 | 90 | 108 |
| HP-202511 | 100 | 1 | 215 | 99 | 110 |
| HP-202512 | 103 | 1 | 215 | 108 | 111 |
| HP-202601 | 106 | 1 | 215 | 105 | 113 |
| HP-202602 | 109 | 1 | 215 | 94 | 113 |
| HP-202603 | 110 | 1 | 215 | 117 | 114 |
| HP-202604 | 112 | 1 | 215 | 117 | 115 |
| HP-202605 | 113 | 1 | 215 | 125 | 116 |
| HP-202606 | 115 | 1 | 215 | 103 | 119 |
| HP-202607 | 118 | 1 | 215 | 109 | 120 |
| HP-202608 | 119 | 1 | 215 | 118 | 120 |
| HP-202609 | 119 | 1 | 215 | 117 | 120 |

202610's benefit-period row has status `O` and no run date; it is listed in `notHoldout`
with `expectedOutput: null`.
