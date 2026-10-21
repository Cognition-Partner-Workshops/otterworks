# Parity: dw.usp_build_producer_scorecard (first-pass)

Run at 2026-10-21 21:10 UTC.

L1 red (46 vs 0), L2 red (10 columns drift), L3 red (0.0% hash match), L4 red (25 sampled diffs)

| Level | Result | Detail |
|---|---|---|
| L1 counts | red | legacy 46, snowflake 0 |
| L2 profiles | red | drift in: scorecard_date, region_code, producer_code, producer_name, agency_name, tier_name, policy_count, claim_count, written_premium, row_status |
| L3 row hash | red | 0/46 keys match (0.0%) |
| L4 samples | red | 25 diffs sampled |

## L2 drift

| Column | Legacy | Snowflake |
|---|---|---|
| scorecard_date | `{"count": 46, "nulls": 0, "distinct": 1, "min": "2026-09-30", "max": "2026-09-30", "min_len": 10, "max_len": 10}` | `{"count": 0, "nulls": 0, "distinct": 0}` |
| region_code | `{"count": 46, "nulls": 0, "distinct": 6, "min": "MW", "max": "SW", "min_len": 2, "max_len": 2}` | `{"count": 0, "nulls": 0, "distinct": 0}` |
| producer_code | `{"count": 46, "nulls": 0, "distinct": 41, "min": "P1004", "max": "~REGION", "min_len": 5, "max_len": 7}` | `{"count": 0, "nulls": 0, "distinct": 0}` |
| producer_name | `{"count": 46, "nulls": 6, "distinct": 36, "min": "Ana Moreau", "max": "Sam Quintero", "min_len": 9, "max_len": 15}` | `{"count": 0, "nulls": 0, "distinct": 0}` |
| agency_name | `{"count": 46, "nulls": 6, "distinct": 6, "min": "Bluewater Insurance Group", "max": "Summit Risk Partners", "min_len": 14, "max_len": 25}` | `{"count": 0, "nulls": 0, "distinct": 0}` |
| tier_name | `{"count": 46, "nulls": 6, "distinct": 1, "min": "Silver", "max": "Silver", "min_len": 6, "max_len": 6}` | `{"count": 0, "nulls": 0, "distinct": 0}` |
| policy_count | `{"count": 46, "nulls": 0, "distinct": 37, "min": "0", "max": "191", "sum": "3809"}` | `{"count": 0, "nulls": 0, "distinct": 0}` |
| claim_count | `{"count": 46, "nulls": 6, "distinct": 26, "min": "1", "max": "43", "sum": "656"}` | `{"count": 0, "nulls": 0, "distinct": 0}` |
| written_premium | `{"count": 46, "nulls": 6, "distinct": 40, "min": "5642.44", "max": "216799.14", "sum": "3965741.61"}` | `{"count": 0, "nulls": 0, "distinct": 0}` |
| row_status | `{"count": 46, "nulls": 0, "distinct": 3, "min": "LOADED", "max": "PRODUCER", "min_len": 6, "max_len": 8}` | `{"count": 0, "nulls": 0, "distinct": 0}` |

## L4 sampled diffs

| Key | Column | Legacy | Snowflake |
|---|---|---|---|
| MW/P1009 | (row) | present | missing |
| MW/P1015 | (row) | present | missing |
| MW/P1039 | (row) | present | missing |
| MW/P1045 | (row) | present | missing |
| MW/p1003 | (row) | present | missing |
| MW/p1021 | (row) | present | missing |
| MW/p1027 | (row) | present | missing |
| MW/p1033 | (row) | present | missing |
| MW/p1051 | (row) | present | missing |
| MW/p1057 | (row) | present | missing |
| MW/~REGION | (row) | present | missing |
| NE/P1019 | (row) | present | missing |
| NE/P1025 | (row) | present | missing |
| NE/P1049 | (row) | present | missing |
| NE/P1055 | (row) | present | missing |
| NE/p1001 | (row) | present | missing |
| NE/p1007 | (row) | present | missing |
| NE/p1013 | (row) | present | missing |
| NE/p1031 | (row) | present | missing |
| NE/p1037 | (row) | present | missing |
| NE/p1043 | (row) | present | missing |
| NE/~REGION | (row) | present | missing |
| NW/~REGION | (row) | present | missing |
| PR/~REGION | (row) | present | missing |
| SE/P1014 | (row) | present | missing |
