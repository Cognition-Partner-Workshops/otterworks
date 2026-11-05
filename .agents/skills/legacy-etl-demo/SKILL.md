---
name: legacy-etl-demo
description: How to run and verify the legacy polyglot batch estate under etl/legacy-extra/ (CUSTBILL chain) for the Databricks migration demo.
---

# Legacy ETL batch estate (etl/legacy-extra/)

CLI-only demo estate; no web UI. The estate lives on the `tech-partnerships` branch (added by PR #842) — it does not exist on `main`; check out `tech-partnerships` (or a branch derived from it) before following these steps. Requires `ksh` (`sudo apt-get install -y ksh`) and, for the SFTP fixture, docker + `sshpass`.

## Run the chain
- `export OTTERWORKS_LEGACY_ROOT=/tmp/otterworks-legacy-<something>` for an isolated run root (default /tmp/otterworks-legacy). Dirs: sftp-drop/upload, incoming, archive, parsed, reports.
- `make legacy-etl-list` — list jobs.
- `make legacy-etl-gen-data NS=dev` — deterministic generator (same NS ⇒ byte-identical files; case-insensitive: dev==DEV; anagram-safe: ved differs). Extra args via `perl etl/legacy-extra/tools/gen_sample_data.pl <NS> <NFILES> <ROWS>`.
- `make legacy-etl-run JOB=sftp_ingest_poll|parse_custbill_fixedwidth|finance_excel_report|run_all` in that order. run_all uses `RUN_ALL_SLEEP` (Makefile defaults it to 0; the script alone defaults 600s).

## Verify
- parsed/*.psv: 6 pipe fields, ISO dates, 2-decimal amounts, ccy USD/EUR/GBP, rt 01/02.
- reports/finance_billing_YYYYMMDD.csv (and byte-identical .xls): recompute with
  `cat parsed/*.psv | awk -F'|' '{k=$5","(($6=="01")?"INVOICE":"CREDIT"); c[k]++; t[k]+=$4} END{for(k in c) printf "%s,%d,%.2f\n",k,c[k],t[k]}'` and compare.
- Fresh empty root: finance_excel_report must still exit 0 with header-only report.

## SFTP fixture
- `make legacy-sftp-up` (passes LEGACY_SFTP_UID=$(id -u) so the bind-mounted drop dir is writable by both host and container), then
  `sshpass -p mvsprod sftp -P 52222 -o StrictHostKeyChecking=no mainframe@127.0.0.1` and `put <file> upload/`.
- Ingest must both stage the file to incoming/ AND delete it from the drop dir (proves uid mapping works). `make legacy-sftp-down` to clean up.

## Candidate parity and local Spark
- `make -C etl/legacy-extra parity CANDIDATE=legacy` self-checks dev, qa, committed edge fixtures and an empty drop. `make -C etl/legacy-extra parity-test` includes a deliberately wrong candidate and an exit-7 candidate; both must fail parity.
- `make -C etl/legacy-extra parity CANDIDATE='<shell command>'` runs a trusted command from the repo root once per case. Read `OTTERWORKS_LEGACY_ROOT/sftp-drop/upload`; produce `incoming/*.dat.done`, `parsed/*.psv` and one `reports/finance_billing_*.csv` plus `.xls`, then exit 0. Each invocation starts with a fresh root. The command owns the whole chain; no Spark implementation is supplied.
- The stdlib harness compares final stage artifacts byte-for-byte, including incoming contents and the emptied drop. The report stamp may differ; each root must contain exactly one CSV and XLS. Markdown/JSON tables, roots and logs stay in `etl/legacy-extra/reports/parity/` (ignored). Archive timestamps, stdout and global lock files are outside the parity contract. Timeout defaults to 120 seconds per process; use `python3 etl/legacy-extra/parity/harness.py --timeout 600` for slower commands.
- `source "$HOME/.sdkman/bin/sdkman-init.sh"`; explicitly `export JAVA_HOME="$HOME/.sdkman/candidates/java/current"` if the inherited value still points at Java 11. `make -C etl/legacy-extra spark-venv` installs PySpark 4.0.1; `make -C etl/legacy-extra spark-smoke` counts generated text rows using `local[*]` (Java 21.0.7 verified). Native Hadoop and incubator-vector warnings are expected locally. PySpark 3.5 was not tested.
- PR #1885's `tools/parity.sh` supplied the fresh-root, union-of-files comparison idea. The new harness accepts arbitrary commands and avoids deleting shared lock files; none of that PR's Python ports or clock shims are included.
- `parity/fixtures/CUSTBILL_EDGES.dat` produces four PSV rows: HDR/TRL disappear, trailing name spaces disappear, `02` credits remain positive, `99` becomes `UNKNOWN(99)` in the report, and the 12-digit maximum becomes `9999999999.99`. The deliberately incorrect trailer count (99 vs 4) is only logged. EUR/GBP/USD stay separate; report rows sort by currency then raw record type. `CUSTBILL_HEADER_ONLY.dat` produces a zero-byte PSV, while an empty drop produces header-only CSV/XLS. XLS is a byte copy of CSV.

## Gotchas
- Intentional legacy quirks (do NOT flag as bugs): /tmp/*.lock files never removed ("lock file present ... continuing anyway" messages are expected), 2>/dev/null||true suppression, hardcoded prod/uat hostname branches, plaintext mvsprod credential, /tmp/cb_body.$$ temp file.
- mawk (default awk) does not support `{n}` regex intervals — use grep -E for field validation, not awk regexes.

## Spark replacement (etl/custbill-spark/)

- `make -C etl/custbill-spark chain ROOT=<estate>` runs the local Spark rebuild (ingest -> parse -> report), one PySpark job per legacy stage, with flock mutual exclusion, typed validation, trailer reconciliation and JSON ledgers under `<estate>/control/`. `STRICT=1` quarantines bad files.
- `make -C etl/custbill-spark parity` prints the byte-for-byte parity table of legacy vs Spark on dev, qa, edges, empty; `make -C etl/custbill-spark recon` adds the idempotent rerun and planted-anomaly checks and writes `docs/tech-partnerships/recon/custbill-spark-chain.recon.json`.
- `make -C etl/custbill-spark test` runs the unit tests, including byte-equivalence of the record/report functions against the real awk and Perl scripts.
- A scheduled Devin automation runs `make -C etl/custbill-spark parity` and `make -C etl/custbill-spark recon` nightly against `tech-partnerships` (not a GitHub schedule). Fresh-clone setup and the deficiency-by-deficiency status table are in `etl/custbill-spark/README.md`. PR CI runs Spark tests and candidate parity in `.github/workflows/tp-golden-smoke.yml`.
