# Parity: dw.usp_build_producer_scorecard (fixture-mixed-case-before)

Run at 2026-10-21 21:53 UTC.

L1 red (46 vs 47), L2 red (10 columns drift), L3 red (93.62% hash match), L4 red (3 sampled diffs)

| Level | Result | Detail |
|---|---|---|
| L1 counts | red | legacy 46, snowflake 47 |
| L2 profiles | red | drift in: scorecard_date, region_code, producer_code, producer_name, agency_name, tier_name, policy_count, claim_count, written_premium, row_status |
| L3 row hash | red | 44/47 keys match (93.62%) |
| L4 samples | red | 3 diffs sampled |

## L2 drift

| Column | Legacy | Snowflake |
|---|---|---|
| scorecard_date | `{"count": 46, "nulls": 0, "distinct": 1, "min": "2026-09-30", "max": "2026-09-30", "min_len": 10, "max_len": 10}` | `{"count": 47, "nulls": 0, "distinct": 1, "min": "2026-09-30", "max": "2026-09-30", "min_len": 10, "max_len": 10}` |
| region_code | `{"count": 46, "nulls": 0, "distinct": 6, "min": "MW", "max": "SW", "min_len": 2, "max_len": 2}` | `{"count": 47, "nulls": 0, "distinct": 6, "min": "MW", "max": "SW", "min_len": 2, "max_len": 2}` |
| producer_code | `{"count": 46, "nulls": 0, "distinct": 41, "min": "P1004", "max": "~REGION", "min_len": 5, "max_len": 7}` | `{"count": 47, "nulls": 0, "distinct": 42, "min": "P1003", "max": "~REGION", "min_len": 5, "max_len": 7}` |
| producer_name | `{"count": 46, "nulls": 6, "distinct": 36, "min": "Ana Moreau", "max": "Sam Quintero", "min_len": 9, "max_len": 15}` | `{"count": 47, "nulls": 6, "distinct": 36, "min": "Ana Moreau", "max": "Sam Quintero", "min_len": 9, "max_len": 15}` |
| agency_name | `{"count": 46, "nulls": 6, "distinct": 6, "min": "Bluewater Insurance Group", "max": "Summit Risk Partners", "min_len": 14, "max_len": 25}` | `{"count": 47, "nulls": 6, "distinct": 6, "min": "Bluewater Insurance Group", "max": "Summit Risk Partners", "min_len": 14, "max_len": 25}` |
| tier_name | `{"count": 46, "nulls": 6, "distinct": 1, "min": "Silver", "max": "Silver", "min_len": 6, "max_len": 6}` | `{"count": 47, "nulls": 6, "distinct": 1, "min": "Silver", "max": "Silver", "min_len": 6, "max_len": 6}` |
| policy_count | `{"count": 46, "nulls": 0, "distinct": 36, "min": "0", "max": "191", "sum": "3814"}` | `{"count": 47, "nulls": 0, "distinct": 38, "min": "0", "max": "191", "sum": "3815"}` |
| claim_count | `{"count": 46, "nulls": 6, "distinct": 26, "min": "1", "max": "43", "sum": "657"}` | `{"count": 47, "nulls": 6, "distinct": 26, "min": "1", "max": "43", "sum": "657"}` |
| written_premium | `{"count": 46, "nulls": 6, "distinct": 40, "min": "5642.44", "max": "216799.14", "sum": "3965841.61"}` | `{"count": 47, "nulls": 6, "distinct": 41, "min": "100", "max": "216799.14", "sum": "3965841.61"}` |
| row_status | `{"count": 46, "nulls": 0, "distinct": 3, "min": "LOADED", "max": "PRODUCER", "min_len": 6, "max_len": 8}` | `{"count": 47, "nulls": 0, "distinct": 3, "min": "LOADED", "max": "PRODUCER", "min_len": 6, "max_len": 8}` |

## L4 sampled diffs

| Key | Column | Legacy | Snowflake |
|---|---|---|---|
| MW/P1003 | (row) | missing | present |
| MW/p1003 | policy_count | `65` | `60` |
| MW/p1003 | claim_count | `10` | `9` |
| MW/p1003 | written_premium | `56166.9` | `56066.9` |
| MW/~REGION | policy_count | `10` | `11` |
