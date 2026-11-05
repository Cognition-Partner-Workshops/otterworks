# CUSTBILL chain on local Spark

Replacement for the three legacy CUSTBILL jobs in `etl/legacy-extra/jobs/`
(KornShell SFTP poll, bash/awk fixed-width parser, Perl finance report). One
PySpark job per legacy stage, all running on `local[*]`, reading the same drop
files and writing the same `incoming/`, `parsed/` and `reports/` artifacts byte
for byte. The legacy scripts stay untouched: they are the reference that
`etl/legacy-extra/parity/harness.py` runs against.

| Legacy job | Spark job | Output |
| --- | --- | --- |
| `sftp_ingest_poll.ksh` | `custbill_spark/ingest.py` | `incoming/CUSTBILL*.dat`, `archive/` |
| `parse_custbill_fixedwidth.sh` | `custbill_spark/parse.py` | `parsed/CUSTBILL*.psv`, `incoming/*.dat.done` |
| `finance_excel_report.pl` | `custbill_spark/report.py` | `reports/finance_billing_YYYYMMDD.{csv,xls}` |
| `run_all.sh` + `crontab` | `custbill_spark/__main__.py chain` + scheduled Devin automation | explicit stage order, one run at a time |

## Run

```sh
make -C etl/legacy-extra spark-venv                 # pinned pyspark into etl/legacy-extra/.venv (needs Java 17+)
make legacy-etl-gen-data NS=dev            # legacy generator drops two files into $OTTERWORKS_LEGACY_ROOT
make -C etl/custbill-spark chain ROOT=/tmp/otterworks-legacy          # ingest -> parse -> report
make -C etl/custbill-spark chain ROOT=/tmp/otterworks-legacy STRICT=1 # quarantine bad files instead
etl/custbill-spark/bin/custbill-spark parse --root /tmp/otterworks-legacy   # a single stage
```

Configuration is environment only (no hostname branching):

| Variable | Default | Meaning |
| --- | --- | --- |
| `CUSTBILL_ROOT` (or `OTTERWORKS_LEGACY_ROOT`) | `/tmp/otterworks-legacy` | estate root with `sftp-drop/upload`, `incoming`, `parsed`, `reports` |
| `CUSTBILL_STRICT` | `0` | `1`: files with invalid records or a trailer mismatch are quarantined and the run fails |
| `CUSTBILL_SPARK_MASTER` | `local[*]` | Spark master |
| `CUSTBILL_DELIVERY_DIR` | unset | if set, the CSV is copied there and the copy is hash-verified |
| `CUSTBILL_DISTRIBUTION` | empty | comma-separated recipients recorded in the report ledger (managed outside the code) |
| `CUSTBILL_ARCHIVE_RETENTION_DAYS` / `CUSTBILL_DONE_RETENTION_DAYS` | `90` / `30` | retention for `archive/` and `incoming/*.done` |

Every run writes a JSON ledger under `<root>/control/<stage>/` (staged, deferred
and failed files; per-file record counts, trailer reconciliation and invalid
records with line numbers; report hash and delivery target). Locks live in
`<root>/control/locks/`. `control/` is outside the directories the legacy chain
writes, so it does not affect parity.

## Proving parity

```sh
make -C etl/custbill-spark test     # unit tests + byte-equivalence of the record/report functions against the real awk and Perl
make -C etl/custbill-spark parity   # parity table: legacy chain vs Spark chain on dev, qa, edges, empty
make -C etl/custbill-spark recon    # parity + second run on the same estate (idempotency) + planted anomalies -> recon JSON
```

The recon report is committed at `docs/tech-partnerships/recon/custbill-spark-chain.recon.json`
and validated by `make tp-validate-recon`. The contract is
`docs/tech-partnerships/contracts/custbill-spark-chain.contract.json`.

## Nightly drift check

The nightly rerun is a scheduled Devin automation against `tech-partnerships`,
not a GitHub schedule. From a fresh clone on an Ubuntu host, run:

```sh
git checkout tech-partnerships
sudo apt-get update
sudo apt-get install -y ksh perl make python3-venv openjdk-17-jdk-headless
export JAVA_HOME="$(dirname "$(dirname "$(readlink -f /usr/bin/java)")")"
export PATH="$JAVA_HOME/bin:$PATH"
export SPARK_LOCAL_IP=127.0.0.1
make -C etl/legacy-extra spark-venv
etl/legacy-extra/.venv/bin/python -m pip install uv
export PATH="$PWD/etl/legacy-extra/.venv/bin:$PATH"
make -C etl/custbill-spark parity
make -C etl/custbill-spark recon
make tp-validate-recon FILE=docs/tech-partnerships/recon/custbill-spark-chain.recon.json
```

Retain `etl/legacy-extra/reports/parity/` (tables, roots and logs) and the recon
JSON as evidence; report any nonzero exit as drift. PR CI runs the Spark tests
and candidate parity in `.github/workflows/tp-golden-smoke.yml`.

## Addendum deficiencies

Status of every item in `etl/legacy-extra/ETL_UPGRADE_GUIDE_ADDENDUM.md`:

| Deficiency | Status | How |
| --- | --- | --- |
| Hard-coded `/data/otterworks` paths, hostname branching | fixed | `config.py`: `CUSTBILL_ROOT`/`--root` only |
| Stale `/tmp/sftp_ingest.lock`, "running anyway" | fixed | `fcntl.flock` per stage and for the chain; a second run exits 3 instead of running twice |
| Size-settle polling to detect complete uploads | fixed | `ingest.completeness`: a file is staged when it ends with its `TRL` record or matches its `.sha256` manifest; partial-suffix or incomplete files stay in the drop for the next run |
| Overlapping cron schedules | fixed | one `chain` entry point, serialized by the chain lock; nightly reruns use fresh harness roots |
| `sleep 600` as dependency management | fixed | `run_chain` starts each stage when the previous one returns; a stage failure stops the chain |
| Errors to `/dev/null`, exit 0 on failure | fixed | every stage logs to stderr and raises; the CLI exits 1 with a traceback, 3 on lock contention |
| No schema validation, no trailer reconciliation | fixed | `parse.typed_frame`/`parse.quality`: width, customer, name, date, amount, currency, record type checked per record; `TRL` count reconciled against body records; results in the parse ledger; `--strict` quarantines |
| Untyped columns, invalid dates/amounts pass through | fixed (ledger) / kept (output) | typed Spark columns drive validation; the `.psv` bytes still follow the awk rules because parity pins them. Strict mode is the switch for rejecting instead |
| Report "Excel" file is a renamed CSV | kept, documented | finance accepts the cutover only on byte-identical reports, and the parity harness compares the `.xls` bytes. A real workbook is a one-line change in `report.py` once finance signs off the new format |
| Hard-coded recipients, unverified sendmail | fixed | delivery is a hash-verified copy to `CUSTBILL_DELIVERY_DIR`; recipients come from `CUSTBILL_DISTRIBUTION` and are recorded in the ledger. A mail relay is not exercised (listed under `unverified_paths` in the recon) |
| Orphaned temp files | fixed | `write_atomic` writes next to the target and renames; the temp file is removed on failure |
| No retention / lifecycle | fixed | `purge_older_than` on `archive/` and `incoming/*.done`, retention in days via environment |
| Perl 5.005 style, untestable code | fixed | Python package with unit tests and legacy-equivalence tests (`tests/`) |
| Trailing-space trimming, `UNKNOWN(rt)` label, bytewise key order, header-only `.dat` -> zero-byte `.psv`, empty estate -> header-only report | kept on purpose | legacy semantics the harness compares byte for byte |

## Numeric note

The legacy Perl sums the amounts as doubles; the Spark job sums exact decimals.
Both print the same cents as long as the double accumulation error stays under
half a cent, which holds for totals below about 10^13 per group. Amounts in the
`.psv` are always two-decimal strings produced by the parser, so no rounding
happens before the sum.
