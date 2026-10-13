Staging parity pkg_billing_core PASS 7 / 7 differing_keys=0

SQL Server `stg.stg_billing_plans` vs Snowflake `STAGING.STG_BILLING_PLANS`, keys id, 9 compared columns.

Not compared:
- `extracted_at`: @[System::StartTime], the server clock when the package ran; differs on every run

### Other destinations

pkg_billing_core lands three tables; the gate takes one table per spec, so the other two
entries under `additional_destinations` in `gate/staging/pkg_billing_core.yaml` were gated with
the same `run_staging_gate` (scratch output, not recorded in `OPS.PARITY_LEDGER`), for both
2026-09-15 and 2026-09-30:

- `Staging parity pkg_billing_core PASS 60 / 60 differing_keys=0` (stg.stg_billing_tenants vs STAGING.STG_BILLING_TENANTS, 5 compared columns)
- `Staging parity pkg_billing_core PASS 72 / 72 differing_keys=0` (stg.stg_billing_subscriptions vs STAGING.STG_BILLING_SUBSCRIPTIONS, 7 compared columns)

The package does not read the business date or a watermark, so the stg tables are identical for both dates.

### Business decisions

Explanation: Plan active flag. DER Normalise timestamps sets `active = (DT_BOOL)(LOWER(active) == "true")`, but billing_plans.csv carries `t`/`f`, so the comparison is never true and all 7 plans land in stg.stg_billing_plans with active = 0, including the 6 plans the file marks `t` (starter/growth/scale monthly and annual); only growth-2019 is genuinely inactive. dim.dim_plan.is_active inherits the zero. The staging model keeps the legacy expression so parity passes; a correct Snowflake version would map `t`/`true`/`1` to true (6 active, 1 inactive), and the data owners should decide before anything downstream filters on is_active.

Explanation: Per-GB overage rate rounding. `overage_cents_per_gb = (DT_I4)ROUND(overage_rate * 100, 0)` turns the 6-decimal rate into whole cents (half-up, via a float multiply). Today's rates (0.25, 0.18, 0.10, 0.22) convert exactly, so 0 of 7 rows lose value, but any sub-cent rate (e.g. 0.1850) would be billed as 19 cents. Kept as-is; a correct version would carry the rate as NUMBER(12,4) cents or keep using overage_rate.

Explanation: Included bytes conversion. `included_bytes = (DT_I8)included_units * 1073741824` treats an included unit as a binary GiB and truncates any fractional unit before multiplying. All 7 plans have whole units (50, 500, 5000), so no row is affected today. Kept; a correct version would document the unit as GiB (or use 10^9 if the price book means GB) and reject fractional units instead of truncating.

Explanation: Tax-exempt default. `tax_exempt = (DT_BOOL)(tax_exempt == "t")` is case-sensitive and treats a blank, `T`, `true` or `1` as not exempt. The file has 7 `t` and 53 `f`, so 0 of 60 tenants are defaulted today. Kept; a correct version would accept the usual true spellings and fail or flag unknown values rather than silently charging tax.

Explanation: Region lookup with no match. LKP Tenant region joins billing_tenants.id to billing_tenant_regions.tenant_id and, in the replay, a tenant with no region row is kept with region_code NULL (SSIS's default would fail the component). All 60 tenants match today, so 0 rows get NULL. Kept as a left join; a correct version would route unmatched tenants to an error output or an explicit `unknown` region.

Explanation: Subscription dates. starts_on, ends_on and suspended_on are cast with (DT_DBTIMESTAMP2,7) and land in date columns, so any time of day would be dropped. The file has date-only values (72 starts_on, 12 ends_on, 0 suspended_on), so nothing is truncated today. Kept.
