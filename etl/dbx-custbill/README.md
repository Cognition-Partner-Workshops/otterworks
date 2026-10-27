# CUSTBILL wave-0 scaffold

Wave 0 creates the landing schemas and volume and deploys paused job placeholders; it loads no table data.
Validate: `databricks bundle validate -t migration`
Deploy: `databricks bundle deploy -t migration`

Both `custbill_chain` and `custbill_recon` are PAUSED.

Decisions:
- Core: Delta `bronze.custbill_raw_lines` → `silver.custbill_records` → `gold.finance_billing_report`.
- Pipeline: Lakeflow Declarative Pipeline (MVs + expectations) run from the job.
- Orchestration: this one job replaces `run_all.sh` and the cron.
- Consumer: a gold table plus a CSV export task that also writes the byte-identical `.xls` copy.
- Data dependency: keep the CUSTBILL fixed-width drop contract, with Auto Loader over `bronze.landing`.
