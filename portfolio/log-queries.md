# Access-log queries

Every traffic number in `assessment-report.md` and `assessment-report.csv` comes from one of the commands below. Each output block is that command's complete stdout, captured by running the command exactly as written, in a fresh empty directory, with the AWS CLI and jq 1.6. Per-app commands after the first one read the files that the first one downloads.

The logs are under `s3://otterworks-data-lake-dev/appassess/appassess-20261023-k4/access-logs/<application>/`: one JSONL file per day, 2026-07-25 to 2026-10-22. **The rows are synthetic and deterministic:** every row has `"synthetic": true`, and the files are written by [scripts/appassess/generate-access-logs.py](https://github.com/Cognition-Partner-Workshops/otterworks/blob/f57a3f76be3d44aee6d352d2d293d8ddf75c8505/scripts/appassess/generate-access-logs.py).

## S3 copy matches the generator

Run from the repository root at the pinned commit:

```bash
python3 scripts/appassess/generate-access-logs.py --out regen && aws s3 sync --only-show-errors s3://otterworks-data-lake-dev/appassess/appassess-20261023-k4/access-logs/ s3copy/ && diff -r s3copy regen && echo IDENTICAL
```

```text
wrote 5 applications x 90 days under regen
IDENTICAL
```

## legacy-portal

1. Download, then count rows by source, method, path and status. This is the query in the CSV's `evidence` column.

```bash
aws s3 sync --only-show-errors s3://otterworks-data-lake-dev/appassess/appassess-20261023-k4/access-logs/legacy-portal/ legacy-portal/ && cat legacy-portal/*/*/*.jsonl | jq -r '[.source,.method,.path,(.status|tostring)]|@tsv' | sort | uniq -c
```

```text
  38163 legacy-portal	GET	/portal/accounts	200
   2001 legacy-portal	GET	/portal/accounts	500
  38655 legacy-portal	GET	/portal/catalog	200
   2067 legacy-portal	GET	/portal/catalog	500
  38627 legacy-portal	GET	/portal/login	200
   2043 legacy-portal	GET	/portal/login	500
  38378 legacy-portal	GET	/portal/orders	200
   2066 legacy-portal	GET	/portal/orders	500
```

2. First and last day on file.

```bash
ls legacy-portal/*/*/*.jsonl | sed -n '1p;$p'
```

```text
legacy-portal/2026/07/25.jsonl
legacy-portal/2026/10/22.jsonl
```

3. Rows per day: each output line is `<number of days> <rows that day>`.

```bash
cat legacy-portal/*/*/*.jsonl | jq -r '.ts[0:10]' | sort | uniq -c | awk '{print $1}' | sort -n | uniq -c
```

```text
     90 1800
```

4. Totals, status and user-agent split, shares, and a check for non-synthetic rows.

```bash
cat legacy-portal/*/*/*.jsonl | jq -s '{rows: length, days: (map(.ts[0:10]) | unique | length), status: (group_by(.status) | map({key: (.[0].status|tostring), value: length}) | from_entries), user_agent: (group_by(.user_agent) | map({key: .[0].user_agent, value: length}) | from_entries), status_200_pct: ((map(select(.status == 200)) | length) * 100 / length | round), browser_pct: ((map(select(.user_agent | startswith("Mozilla"))) | length) * 100 / length | round), okhttp_pct: ((map(select(.user_agent | startswith("okhttp"))) | length) * 100 / length | round), non_synthetic: (map(select(.synthetic != true)) | length)}'
```

```text
{
  "rows": 162000,
  "days": 90,
  "status": {
    "200": 153823,
    "500": 8177
  },
  "user_agent": {
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5)": 53905,
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)": 54010,
    "okhttp/4.12.0": 54085
  },
  "status_200_pct": 95,
  "browser_pct": 67,
  "okhttp_pct": 33,
  "non_synthetic": 0
}
```

## report-service

1. Download, then count rows by source, method, path and status. This is the query in the CSV's `evidence` column.

```bash
aws s3 sync --only-show-errors s3://otterworks-data-lake-dev/appassess/appassess-20261023-k4/access-logs/report-service/ report-service/ && cat report-service/*/*/*.jsonl | jq -r '[.source,.method,.path,(.status|tostring)]|@tsv' | sort | uniq -c
```

```text
   6253 api-gateway	GET	/api/v1/reports	404
   6347 api-gateway	GET	/api/v1/reports/scheduled	404
```

2. First and last day on file.

```bash
ls report-service/*/*/*.jsonl | sed -n '1p;$p'
```

```text
report-service/2026/07/25.jsonl
report-service/2026/10/22.jsonl
```

3. Rows per day: each output line is `<number of days> <rows that day>`.

```bash
cat report-service/*/*/*.jsonl | jq -r '.ts[0:10]' | sort | uniq -c | awk '{print $1}' | sort -n | uniq -c
```

```text
     90 140
```

4. Totals, status and user-agent split, shares, and a check for non-synthetic rows.

```bash
cat report-service/*/*/*.jsonl | jq -s '{rows: length, days: (map(.ts[0:10]) | unique | length), status: (group_by(.status) | map({key: (.[0].status|tostring), value: length}) | from_entries), user_agent: (group_by(.user_agent) | map({key: .[0].user_agent, value: length}) | from_entries), status_200_pct: ((map(select(.status == 200)) | length) * 100 / length | round), browser_pct: ((map(select(.user_agent | startswith("Mozilla"))) | length) * 100 / length | round), okhttp_pct: ((map(select(.user_agent | startswith("okhttp"))) | length) * 100 / length | round), non_synthetic: (map(select(.synthetic != true)) | length)}'
```

```text
{
  "rows": 12600,
  "days": 90,
  "status": {
    "404": 12600
  },
  "user_agent": {
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5)": 4222,
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)": 4118,
    "okhttp/4.12.0": 4260
  },
  "status_200_pct": 0,
  "browser_pct": 66,
  "okhttp_pct": 34,
  "non_synthetic": 0
}
```

## legacy-billing

1. Download, then count rows by source, method, path and status. This is the query in the CSV's `evidence` column.

```bash
aws s3 sync --only-show-errors s3://otterworks-data-lake-dev/appassess/appassess-20261023-k4/access-logs/legacy-billing/ legacy-billing/ && cat legacy-billing/*/*/*.jsonl | jq -r '[.source,.method,.path,(.status|tostring)]|@tsv' | sort | uniq -c
```

```text
  18420 legacy-billing	GET	/billing/dunning	200
    940 legacy-billing	GET	/billing/dunning	500
  18555 legacy-billing	GET	/billing/invoices	200
   1051 legacy-billing	GET	/billing/invoices	500
  18599 legacy-billing	GET	/billing/usage	200
    935 legacy-billing	GET	/billing/usage	500
```

2. First and last day on file.

```bash
ls legacy-billing/*/*/*.jsonl | sed -n '1p;$p'
```

```text
legacy-billing/2026/07/25.jsonl
legacy-billing/2026/10/22.jsonl
```

3. Rows per day: each output line is `<number of days> <rows that day>`.

```bash
cat legacy-billing/*/*/*.jsonl | jq -r '.ts[0:10]' | sort | uniq -c | awk '{print $1}' | sort -n | uniq -c
```

```text
     90 650
```

4. Totals, status and user-agent split, shares, and a check for non-synthetic rows.

```bash
cat legacy-billing/*/*/*.jsonl | jq -s '{rows: length, days: (map(.ts[0:10]) | unique | length), status: (group_by(.status) | map({key: (.[0].status|tostring), value: length}) | from_entries), user_agent: (group_by(.user_agent) | map({key: .[0].user_agent, value: length}) | from_entries), status_200_pct: ((map(select(.status == 200)) | length) * 100 / length | round), browser_pct: ((map(select(.user_agent | startswith("Mozilla"))) | length) * 100 / length | round), okhttp_pct: ((map(select(.user_agent | startswith("okhttp"))) | length) * 100 / length | round), non_synthetic: (map(select(.synthetic != true)) | length)}'
```

```text
{
  "rows": 58500,
  "days": 90,
  "status": {
    "200": 55574,
    "500": 2926
  },
  "user_agent": {
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5)": 19328,
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)": 19694,
    "okhttp/4.12.0": 19478
  },
  "status_200_pct": 95,
  "browser_pct": 67,
  "okhttp_pct": 33,
  "non_synthetic": 0
}
```

## db2-retention-archive

1. Download, then count rows by source, method, path and status. This is the query in the CSV's `evidence` column.

```bash
aws s3 sync --only-show-errors s3://otterworks-data-lake-dev/appassess/appassess-20261023-k4/access-logs/db2-retention-archive/ db2-retention-archive/ && cat db2-retention-archive/*/*/*.jsonl | jq -r '[.source,.method,.path,(.status|tostring)]|@tsv' | sort | uniq -c
```

```text
   1040 db2-archive-batch	GET	DOCARCH:SELECT	200
     61 db2-archive-batch	GET	DOCARCH:SELECT	500
   1002 db2-archive-batch	GET	FILEAUD:SELECT	200
     57 db2-archive-batch	GET	FILEAUD:SELECT	500
```

2. First and last day on file.

```bash
ls db2-retention-archive/*/*/*.jsonl | sed -n '1p;$p'
```

```text
db2-retention-archive/2026/07/25.jsonl
db2-retention-archive/2026/10/22.jsonl
```

3. Rows per day: each output line is `<number of days> <rows that day>`.

```bash
cat db2-retention-archive/*/*/*.jsonl | jq -r '.ts[0:10]' | sort | uniq -c | awk '{print $1}' | sort -n | uniq -c
```

```text
     90 24
```

4. Totals, status and user-agent split, shares, and a check for non-synthetic rows.

```bash
cat db2-retention-archive/*/*/*.jsonl | jq -s '{rows: length, days: (map(.ts[0:10]) | unique | length), status: (group_by(.status) | map({key: (.[0].status|tostring), value: length}) | from_entries), user_agent: (group_by(.user_agent) | map({key: .[0].user_agent, value: length}) | from_entries), status_200_pct: ((map(select(.status == 200)) | length) * 100 / length | round), browser_pct: ((map(select(.user_agent | startswith("Mozilla"))) | length) * 100 / length | round), okhttp_pct: ((map(select(.user_agent | startswith("okhttp"))) | length) * 100 / length | round), non_synthetic: (map(select(.synthetic != true)) | length)}'
```

```text
{
  "rows": 2160,
  "days": 90,
  "status": {
    "200": 2042,
    "500": 118
  },
  "user_agent": {
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5)": 737,
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)": 738,
    "okhttp/4.12.0": 685
  },
  "status_200_pct": 95,
  "browser_pct": 68,
  "okhttp_pct": 32,
  "non_synthetic": 0
}
```

## legacy-share-links

1. Download, then count rows by source, method, path and status. This is the query in the CSV's `evidence` column.

```bash
aws s3 sync --only-show-errors s3://otterworks-data-lake-dev/appassess/appassess-20261023-k4/access-logs/legacy-share-links/ legacy-share-links/ && cat legacy-share-links/*/*/*.jsonl | jq -r '[.source,.method,.path,(.status|tostring)]|@tsv' | sort | uniq -c
```

```text
     90 legacy-share-links	POST	/share-links/admin/purge-expired	200
```

2. First and last day on file.

```bash
ls legacy-share-links/*/*/*.jsonl | sed -n '1p;$p'
```

```text
legacy-share-links/2026/07/25.jsonl
legacy-share-links/2026/10/22.jsonl
```

3. Rows per day: each output line is `<number of days> <rows that day>`.

```bash
cat legacy-share-links/*/*/*.jsonl | jq -r '.ts[0:10]' | sort | uniq -c | awk '{print $1}' | sort -n | uniq -c
```

```text
     90 1
```

4. Totals, status and user-agent split, shares, and a check for non-synthetic rows.

```bash
cat legacy-share-links/*/*/*.jsonl | jq -s '{rows: length, days: (map(.ts[0:10]) | unique | length), status: (group_by(.status) | map({key: (.[0].status|tostring), value: length}) | from_entries), user_agent: (group_by(.user_agent) | map({key: .[0].user_agent, value: length}) | from_entries), status_200_pct: ((map(select(.status == 200)) | length) * 100 / length | round), browser_pct: ((map(select(.user_agent | startswith("Mozilla"))) | length) * 100 / length | round), okhttp_pct: ((map(select(.user_agent | startswith("okhttp"))) | length) * 100 / length | round), non_synthetic: (map(select(.synthetic != true)) | length)}'
```

```text
{
  "rows": 90,
  "days": 90,
  "status": {
    "200": 90
  },
  "user_agent": {
    "otterworks-nightly/2.3": 90
  },
  "status_200_pct": 100,
  "browser_pct": 0,
  "okhttp_pct": 0,
  "non_synthetic": 0
}
```

5. Time of day, client, method, path and user agent of every row.

```bash
cat legacy-share-links/*/*/*.jsonl | jq -r '[.ts[11:19],.client_ip,.method,.path,.user_agent]|@tsv' | sort | uniq -c
```

```text
     90 02:15:03	10.20.9.14	POST	/share-links/admin/purge-expired	otterworks-nightly/2.3
```

6. GET requests (that is, share-link redirects) in the 90 days.

```bash
cat legacy-share-links/*/*/*.jsonl | jq -c 'select(.method == "GET")' | wc -l
```

```text
0
```
