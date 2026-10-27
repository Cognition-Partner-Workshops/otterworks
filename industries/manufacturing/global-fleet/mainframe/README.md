# Mainframe country: company-car estate (CA IDMS, ADS, COBOL)

There is no licensed IDMS runtime in this sandbox, so nothing here executes. The source is kept as text, exactly as it was exported from the dictionary and the PDS libraries. The holdout pairs under `holdout/` stand in for the runtime: each pair is a benefit-run input unload and the output the production run produced from it, so any rebuild of the batch can be checked byte for byte without a mainframe.

## Layout

| Path | What it is |
|---|---|
| `schema/FLEETSCH.ddl` | IDMS schema: areas, records, CALC keys, sets |
| `schema/FLEETSS1.ddl` | Subschemas `FLEETSS1` (online dialogs) and `FLEETSS2` (batch, retrieval) |
| `ads/dialogs/` | ADSC dialog definitions |
| `ads/maps/` | MAPC map source |
| `ads/process/` | Premap and response process code |
| `batch/FLEBEN01.cbl` | Monthly company-car benefit run, COBOL with IDMS DML |
| `copybooks/` | Flat-file layouts of the unloads and of the benefit-run output |
| `jcl/` | Unload job and benefit-run job |
| `unload/` | Unload of the production database as at 2026-10-27 |
| `holdout/` | Twelve closed benefit periods, `HP-YYYYMM/IN` and `HP-YYYYMM/OUT` |

## Data format

The unloads are fixed-length records with no line terminators, ASCII text with packed-decimal (COMP-3) money fields. Byte offsets are in `copybooks/LAYOUT.md`, which follows the method in `migration/source/copybooks/FIELD-DERIVATION.md`. `unload/UNLOAD.cnt` and `holdout/PAIRS.sha256` are the control totals.

Money is pounds sterling and distances are miles.
