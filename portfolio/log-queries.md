# Access-log queries

Every traffic claim in `assessment-report.md` and `assessment-report.csv` links to one of the queries below. The logs are under `s3://otterworks-data-lake-dev/appassess/appassess-20261023-k4/access-logs/<application>/`: 90 daily JSONL files per application, 2026-07-25 to 2026-10-22. **The rows are synthetic and deterministic.** Every row has `"synthetic": true`. They were written by [scripts/appassess/generate-access-logs.py](https://github.com/Cognition-Partner-Workshops/otterworks/blob/f57a3f76be3d44aee6d352d2d293d8ddf75c8505/scripts/appassess/generate-access-logs.py). Running that script locally (`python3 scripts/appassess/generate-access-logs.py --out regen`) gives files byte-identical to the S3 copy (`diff -r` is clean).

Each section shows the exact command and its output. The output adds a per-user-agent count (`jq -r .user_agent | sort | uniq -c`) and a check for non-synthetic rows (`jq -c 'select(.synthetic!=true)' | wc -l`).

## legacy-portal

```bash
aws s3 sync s3://otterworks-data-lake-dev/appassess/appassess-20261023-k4/access-logs/legacy-portal/ legacy-portal/ && cat legacy-portal/*/*/*.jsonl | jq -r '[.source,.method,.path,(.status|tostring),.user_agent]|@tsv' | sort | uniq -c
```

```text
files: 90  first: legacy-portal/2026/07/25.jsonl  last: legacy-portal/2026/10/22.jsonl  rows: 162000
  38163 legacy-portal	GET	/portal/accounts	200
   2001 legacy-portal	GET	/portal/accounts	500
  38655 legacy-portal	GET	/portal/catalog	200
   2067 legacy-portal	GET	/portal/catalog	500
  38627 legacy-portal	GET	/portal/login	200
   2043 legacy-portal	GET	/portal/login	500
  38378 legacy-portal	GET	/portal/orders	200
   2066 legacy-portal	GET	/portal/orders	500
-- by user agent
  53905 Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5)
  54010 Mozilla/5.0 (Windows NT 10.0; Win64; x64)
  54085 okhttp/4.12.0
-- non-synthetic rows: 0
```

## report-service

```bash
aws s3 sync s3://otterworks-data-lake-dev/appassess/appassess-20261023-k4/access-logs/report-service/ report-service/ && cat report-service/*/*/*.jsonl | jq -r '[.source,.method,.path,(.status|tostring),.user_agent]|@tsv' | sort | uniq -c
```

```text
files: 90  first: report-service/2026/07/25.jsonl  last: report-service/2026/10/22.jsonl  rows: 12600
   6253 api-gateway	GET	/api/v1/reports	404
   6347 api-gateway	GET	/api/v1/reports/scheduled	404
-- by user agent
   4222 Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5)
   4118 Mozilla/5.0 (Windows NT 10.0; Win64; x64)
   4260 okhttp/4.12.0
-- non-synthetic rows: 0
```

## legacy-billing

```bash
aws s3 sync s3://otterworks-data-lake-dev/appassess/appassess-20261023-k4/access-logs/legacy-billing/ legacy-billing/ && cat legacy-billing/*/*/*.jsonl | jq -r '[.source,.method,.path,(.status|tostring),.user_agent]|@tsv' | sort | uniq -c
```

```text
files: 90  first: legacy-billing/2026/07/25.jsonl  last: legacy-billing/2026/10/22.jsonl  rows: 58500
  18420 legacy-billing	GET	/billing/dunning	200
    940 legacy-billing	GET	/billing/dunning	500
  18555 legacy-billing	GET	/billing/invoices	200
   1051 legacy-billing	GET	/billing/invoices	500
  18599 legacy-billing	GET	/billing/usage	200
    935 legacy-billing	GET	/billing/usage	500
-- by user agent
  19328 Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5)
  19694 Mozilla/5.0 (Windows NT 10.0; Win64; x64)
  19478 okhttp/4.12.0
-- non-synthetic rows: 0
```

## db2-retention-archive

```bash
aws s3 sync s3://otterworks-data-lake-dev/appassess/appassess-20261023-k4/access-logs/db2-retention-archive/ db2-retention-archive/ && cat db2-retention-archive/*/*/*.jsonl | jq -r '[.source,.method,.path,(.status|tostring),.user_agent]|@tsv' | sort | uniq -c
```

```text
files: 90  first: db2-retention-archive/2026/07/25.jsonl  last: db2-retention-archive/2026/10/22.jsonl  rows: 2160
   1040 db2-archive-batch	GET	DOCARCH:SELECT	200
     61 db2-archive-batch	GET	DOCARCH:SELECT	500
   1002 db2-archive-batch	GET	FILEAUD:SELECT	200
     57 db2-archive-batch	GET	FILEAUD:SELECT	500
-- by user agent
    737 Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5)
    738 Mozilla/5.0 (Windows NT 10.0; Win64; x64)
    685 okhttp/4.12.0
-- non-synthetic rows: 0
```

## legacy-share-links

```bash
aws s3 sync s3://otterworks-data-lake-dev/appassess/appassess-20261023-k4/access-logs/legacy-share-links/ legacy-share-links/ && cat legacy-share-links/*/*/*.jsonl | jq -r '[.source,.method,.path,(.status|tostring),.user_agent]|@tsv' | sort | uniq -c
```

```text
files: 90  first: legacy-share-links/2026/07/25.jsonl  last: legacy-share-links/2026/10/22.jsonl  rows: 90
     90 legacy-share-links	POST	/share-links/admin/purge-expired	200
-- by user agent
     90 otterworks-nightly/2.3
-- non-synthetic rows: 0
```
