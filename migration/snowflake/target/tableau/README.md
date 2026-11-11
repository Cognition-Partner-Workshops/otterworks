# Migrated Tableau workbooks

A migrated workbook keeps the legacy file name from `source/tableau/` and its datasource captions, worksheets and dashboard. In each datasource the connection and the custom SQL change:

- The connection: `class='snowflake'`, `server` set to the account host, `dbname` set to the run database `OW_UBW_<TOKEN>`, `schema='MARTS'`, `warehouse` set to `OW_UBW_<TOKEN>_WH`, `service` set to the read-only role `OW_UBW_<TOKEN>_READER` and `username` set to `OW_UBW_<TOKEN>_VIEWER`. No password goes in the file.
- The custom SQL: read the dbt model that replaces the legacy table (for example `mart.mart_overage_charges` becomes `MARTS.BUILD_MART_OVERAGE`) and rewrite T-SQL into Snowflake SQL, such as `COUNT_BIG(*)` into `COUNT(*)` and `TOP (n)` into `LIMIT n`. Keep the `<[Parameters].[Business Date]>` placeholders.

`make sfm-bi-parity RUN=<token> DATE=<date>` runs both copies of every datasource and draws the result in the console. A workbook without a file here shows as still on SQL Server.
