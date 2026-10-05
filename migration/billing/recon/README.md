# Billing recon (plan step `s3.4-recon-script`)

`recon.py` compares Oracle `OW_BILLING` with the Atlas migration database using only
`migration/billing/mapping_spec.json`, `migration/billing/tolerances.json` and the fixture
manifest `migration/billing/fixtures/demo.json`. It replaces the plugin recon harness with
repo-only tooling (python-oracledb + pymongo) and writes a report that conforms to
`docs/tech-partnerships/contracts/schema/recon-report.schema.json`.

For every collection in the mapping spec it checks, per source table:

| check id | what |
|----------|------|
| `<coll>.row_count` | source rows vs documents (embedded: child rows vs elements + quarantine documents) |
| `<coll>.keyed_presence` | every PK has exactly one document; compound `_id` key order per the spec |
| `<coll>.keyed_values` | field-by-field with the mapping applied; `tolerances.json` is exact (0) |
| `<coll>.money_decimal128` | money is `Decimal` vs `Decimal128`; a binary double on either side is a defect |
| `<coll>.<path>.shape_and_order` | embedded arrays keyed by the identity the spec names, ordered as the spec says |
| `invoice_feed_quarantine.*` | orphaned `INVOICE_LINE` rows must land in quarantine exactly |
| `derived_fields.rules` | DD-MON-YY dates parse under RR; CSV lists split only when clean; else the derived field is absent |
| `census_delta.<table>` | the fixture-only `static_seed_version` 2 rows are accounted for explicitly, never a defect |
| `anomalies.<kind>.{source,target}` | planted sets compared as sets (orphans, dirty dates, malformed CSV, EAV spelling matrix); a `--collections` subset skips kinds whose table is outside the run and lists them under `unverified_paths` |

Oracle access is `SELECT` only under `SET TRANSACTION READ ONLY`, with a connection pool
sized from `tolerances.json#source.concurrency` (1 = serial). The principal is refused if it
holds any write privilege. Secrets are referenced by name only (`OW_TP_ORACLE_RO_DSN`,
`MONGODB_ATLAS_URI`); the script never prints them.

## Self-test (gate `g-recon-selftest`)

```sh
uv run --no-project --with pymongo==4.10.1 --with jsonschema==4.25.1 --with rfc3339-validator==0.1.4 \
  python3 migration/billing/recon/recon.py selftest --out migration/billing/recon/out/selftest \
  --mongo-uri mongodb://127.0.0.1:27117        # throwaway local mongod; omit for in-memory
make tp-validate-recon FILE=migration/billing/recon/out/selftest/selftest-faithful.recon.json
```

The self-test synthesises a faithful copy of `demo.json` (row counts per table, the census-delta
PKs, the 37 orphan `line_ids`, the 50 dirty `SIGNUP_DT` and 31 malformed `RELATED_ACCT_IDS`
`cust_ids` with their value histograms, the EAV `(attr_name, attr_value)` matrix), loads it
through the mapping into a loopback mongod (or in memory), and runs the recon four times:

| scenario | planted defect | expected |
|----------|----------------|----------|
| `faithful` | none | `pass` |
| `dropped_row` | one `invoice_feed` document deleted | `fail` (`row_count`, `keyed_presence`) |
| `changed_amount` | `customers.curBalAmt` moved by 0.01 as Decimal128 | `fail` (`keyed_values`) |
| `float_rounded_amount` | `invoice_feed.lines[].amount` stored as a double rounded to 2 places | `fail` (`money_decimal128`) |

Every report is validated against the repo schema; `selftest-summary.json` records the verdicts.
A fixture/self-test report has `run_mode: fixture` and `merge_evidence: false`.

## Live run (merge evidence)

```sh
uv run --no-project --with pymongo==4.10.1 --with oracledb==2.5.1 --with jsonschema==4.25.1 --with rfc3339-validator==0.1.4 \
  python3 migration/billing/recon/recon.py run --mode live --out migration/billing/recon/out/billing.live.recon.json
make tp-validate-recon FILE=migration/billing/recon/out/billing.live.recon.json
```

`--mode live` refuses to run unless the configured secret names are used and neither side
resolves to loopback; `--mode local` (fixture Oracle + local mongod) is for development and is
never merge evidence. Exit status: 0 pass, 1 fail, 2 report does not validate.

## Tests

```sh
uv run --no-project --with pymongo==4.10.1 --with jsonschema==4.25.1 --with pytest python3 -m pytest migration/billing/recon/tests -q
```
