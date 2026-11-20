# sfg1120 — DuckDB backfill evidence

RUN_TOKEN=sfx1119. Snapshot files under ignored `.runs/`; original bad rows retained in `before-backfill.duckdb`.

## Commands

```sh
python warehouse/pipeline/schema_drift.py --column USAGE_DATE
python warehouse/pipeline/load_daily.py --target duckdb --no-build --date 2026-11-10
python warehouse/pipeline/schema_drift.py --column CUSTOMER_ID
python warehouse/pipeline/load_daily.py --target duckdb --no-build --date 2026-11-10 --step backfill
python warehouse/pipeline/load_daily.py --target duckdb --no-build --date 2026-11-10 --step backfill
```

## Rejected unknown date format

```text
ignored extra columns: ACCOUNT_NAME, INVOICE_NUMBER, DISCOUNT_CODE
Traceback (most recent call last):
  File "/home/ubuntu/repos/otterworks/warehouse/pipeline/load_daily.py", line 238, in <module>
    main()
  File "/home/ubuntu/repos/otterworks/warehouse/pipeline/load_daily.py", line 231, in main
    load(args.date, args.step, args.schema, args.warehouse, args.no_build,
  File "/home/ubuntu/repos/otterworks/warehouse/snowflake/telemetry.py", line 47, in wrapped
    result = function(*args, **kwargs)
             ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/ubuntu/repos/otterworks/warehouse/pipeline/load_daily.py", line 160, in load
    return load_duckdb(path, day, schema, db_path)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/ubuntu/repos/otterworks/warehouse/pipeline/load_daily.py", line 80, in load_duckdb
    with duckdb.connect(str(db_path)) as connection:
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/ubuntu/repos/otterworks/warehouse/pipeline/load_daily.py", line 103, in load_duckdb
    validate_casts(connection, columns, expressions,
  File "/home/ubuntu/repos/otterworks/warehouse/pipeline/load_daily.py", line 71, in validate_casts
    raise SafeLoadError("Invalid source casts: " + details)
telemetry.SafeLoadError: Invalid source casts: USAGE_DATE: count=48, sample='11/10/2026'
```

# Backfill diff

| Source day | Snapshot | Rows | Distinct IDs | Duplicate keys | Amount sum | NULL counts |
|---|---|---:|---:|---:|---:|---|
| pipeline/2026-11-09.csv | before | 48 | 48 | 0 | 29340.00 | USAGE_DAILY_ID=0, CUSTOMER_ID=0, USAGE_DATE=0, QUANTITY=0, UNIT_PRICE=0, AMOUNT=0, CURRENCY_CODE=0, CREATED_AT=0, IS_ACTIVE=0, _SRC_FILE=0, USAGE_ID=0, USAGE_DT=0, UNITS=0, SUBSCRIPTION_ID=48, USAGE_TYPE=48 |
| pipeline/2026-11-09.csv | after | 48 | 48 | 0 | 29340.00 | USAGE_DAILY_ID=0, CUSTOMER_ID=0, USAGE_DATE=0, QUANTITY=0, UNIT_PRICE=0, AMOUNT=0, CURRENCY_CODE=0, CREATED_AT=0, IS_ACTIVE=0, _SRC_FILE=0, USAGE_ID=0, USAGE_DT=0, UNITS=0, SUBSCRIPTION_ID=48, USAGE_TYPE=48 |
| pipeline/2026-11-10.csv | before | 48 | 48 | 0 | 29340.00 | USAGE_DAILY_ID=0, CUSTOMER_ID=48, USAGE_DATE=0, QUANTITY=0, UNIT_PRICE=0, AMOUNT=0, CURRENCY_CODE=0, CREATED_AT=0, IS_ACTIVE=0, _SRC_FILE=0, USAGE_ID=0, USAGE_DT=0, UNITS=0, SUBSCRIPTION_ID=48, USAGE_TYPE=48 |
| pipeline/2026-11-10.csv | after | 48 | 48 | 0 | 29340.00 | USAGE_DAILY_ID=0, CUSTOMER_ID=48, USAGE_DATE=0, QUANTITY=0, UNIT_PRICE=0, AMOUNT=0, CURRENCY_CODE=0, CREATED_AT=0, IS_ACTIVE=0, _SRC_FILE=0, USAGE_ID=0, USAGE_DT=0, UNITS=0, SUBSCRIPTION_ID=48, USAGE_TYPE=48 |

pipeline/2026-11-09.csv: **0 changed keys**; identical excluding _LOADED_AT: **True**.


pipeline/2026-11-10.csv: **0 changed keys**; identical excluding _LOADED_AT: **True**.


## Successful backfill, original vs final

# Backfill diff

| Source day | Snapshot | Rows | Distinct IDs | Duplicate keys | Amount sum | NULL counts |
|---|---|---:|---:|---:|---:|---|
| pipeline/2026-11-09.csv | before | 48 | 48 | 0 | 29340.00 | USAGE_DAILY_ID=0, CUSTOMER_ID=0, USAGE_DATE=0, QUANTITY=0, UNIT_PRICE=0, AMOUNT=0, CURRENCY_CODE=0, CREATED_AT=0, IS_ACTIVE=0, _SRC_FILE=0, USAGE_ID=0, USAGE_DT=0, UNITS=0, SUBSCRIPTION_ID=48, USAGE_TYPE=48 |
| pipeline/2026-11-09.csv | after | 48 | 48 | 0 | 29340.00 | USAGE_DAILY_ID=0, CUSTOMER_ID=0, USAGE_DATE=0, QUANTITY=0, UNIT_PRICE=0, AMOUNT=0, CURRENCY_CODE=0, CREATED_AT=0, IS_ACTIVE=0, _SRC_FILE=0, USAGE_ID=0, USAGE_DT=0, UNITS=0, SUBSCRIPTION_ID=48, USAGE_TYPE=48 |
| pipeline/2026-11-10.csv | before | 48 | 48 | 0 | 29340.00 | USAGE_DAILY_ID=0, CUSTOMER_ID=48, USAGE_DATE=0, QUANTITY=0, UNIT_PRICE=0, AMOUNT=0, CURRENCY_CODE=0, CREATED_AT=0, IS_ACTIVE=0, _SRC_FILE=0, USAGE_ID=0, USAGE_DT=0, UNITS=0, SUBSCRIPTION_ID=48, USAGE_TYPE=48 |
| pipeline/2026-11-10.csv | after | 48 | 48 | 0 | 29340.00 | USAGE_DAILY_ID=0, CUSTOMER_ID=0, USAGE_DATE=0, QUANTITY=0, UNIT_PRICE=0, AMOUNT=0, CURRENCY_CODE=0, CREATED_AT=0, IS_ACTIVE=0, _SRC_FILE=0, USAGE_ID=0, USAGE_DT=0, UNITS=0, SUBSCRIPTION_ID=48, USAGE_TYPE=48 |

pipeline/2026-11-09.csv: **0 changed keys**; identical excluding _LOADED_AT: **True**.


pipeline/2026-11-10.csv: **48 changed keys**; identical excluding _LOADED_AT: **False**.


## Second replay, first vs second backfill

# Backfill diff

| Source day | Snapshot | Rows | Distinct IDs | Duplicate keys | Amount sum | NULL counts |
|---|---|---:|---:|---:|---:|---|
| pipeline/2026-11-09.csv | before | 48 | 48 | 0 | 29340.00 | USAGE_DAILY_ID=0, CUSTOMER_ID=0, USAGE_DATE=0, QUANTITY=0, UNIT_PRICE=0, AMOUNT=0, CURRENCY_CODE=0, CREATED_AT=0, IS_ACTIVE=0, _SRC_FILE=0, USAGE_ID=0, USAGE_DT=0, UNITS=0, SUBSCRIPTION_ID=48, USAGE_TYPE=48 |
| pipeline/2026-11-09.csv | after | 48 | 48 | 0 | 29340.00 | USAGE_DAILY_ID=0, CUSTOMER_ID=0, USAGE_DATE=0, QUANTITY=0, UNIT_PRICE=0, AMOUNT=0, CURRENCY_CODE=0, CREATED_AT=0, IS_ACTIVE=0, _SRC_FILE=0, USAGE_ID=0, USAGE_DT=0, UNITS=0, SUBSCRIPTION_ID=48, USAGE_TYPE=48 |
| pipeline/2026-11-10.csv | before | 48 | 48 | 0 | 29340.00 | USAGE_DAILY_ID=0, CUSTOMER_ID=0, USAGE_DATE=0, QUANTITY=0, UNIT_PRICE=0, AMOUNT=0, CURRENCY_CODE=0, CREATED_AT=0, IS_ACTIVE=0, _SRC_FILE=0, USAGE_ID=0, USAGE_DT=0, UNITS=0, SUBSCRIPTION_ID=48, USAGE_TYPE=48 |
| pipeline/2026-11-10.csv | after | 48 | 48 | 0 | 29340.00 | USAGE_DAILY_ID=0, CUSTOMER_ID=0, USAGE_DATE=0, QUANTITY=0, UNIT_PRICE=0, AMOUNT=0, CURRENCY_CODE=0, CREATED_AT=0, IS_ACTIVE=0, _SRC_FILE=0, USAGE_ID=0, USAGE_DT=0, UNITS=0, SUBSCRIPTION_ID=48, USAGE_TYPE=48 |

pipeline/2026-11-09.csv: **0 changed keys**; identical excluding _LOADED_AT: **True**.


pipeline/2026-11-10.csv: **0 changed keys**; identical excluding _LOADED_AT: **True**.


## Pipeline events

```jsonl
{"timestamp": "2026-11-20T17:01:06.816274+00:00", "event": "load_started", "run": "sfx1119"}
{"timestamp": "2026-11-20T17:01:06.934543+00:00", "event": "load_failure", "run": "sfx1119", "error_type": "SafeLoadError", "error_message": "Invalid source casts: USAGE_DATE: count=48, sample='11/10/2026'"}
{"timestamp": "2026-11-20T17:01:07.117148+00:00", "event": "load_started", "run": "sfx1119"}
{"timestamp": "2026-11-20T17:01:07.270711+00:00", "event": "load_success", "run": "sfx1119"}
{"timestamp": "2026-11-20T17:01:07.344910+00:00", "event": "load_started", "run": "sfx1119"}
{"timestamp": "2026-11-20T17:01:07.461254+00:00", "event": "load_success", "run": "sfx1119"}
```

No live Snowflake or Loki run; Snowflake SQL transaction/rollback covered with fake cursors. `_LOADED_AT` is excluded from row equality.
