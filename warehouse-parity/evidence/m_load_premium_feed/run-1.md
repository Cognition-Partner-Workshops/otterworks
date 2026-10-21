# Parity: m_load_premium_feed (run-1)

Run at 2026-10-21 21:10 UTC.

L1 red (1500 vs 0), L2 red (5 columns drift), L3 red (0.0% hash match), L4 red (25 sampled diffs)

| Level | Result | Detail |
|---|---|---|
| L1 counts | red | legacy 1500, snowflake 0 |
| L2 profiles | red | drift in: policy_number, product_code, region_code, premium_amount, effective_date |
| L3 row hash | red | 0/1500 keys match (0.0%) |
| L4 samples | red | 25 diffs sampled |

## L2 drift

| Column | Legacy | Snowflake |
|---|---|---|
| policy_number | `{"count": 1500, "nulls": 0, "distinct": 1500, "min": "PL00100001  ", "max": "PL00101998  ", "min_len": 12, "max_len": 12}` | `{"count": 0, "nulls": 0, "distinct": 0}` |
| product_code | `{"count": 1500, "nulls": 0, "distinct": 5, "min": "AUTO", "max": "UMBR", "min_len": 4, "max_len": 4}` | `{"count": 0, "nulls": 0, "distinct": 0}` |
| region_code | `{"count": 1500, "nulls": 0, "distinct": 6, "min": "MW", "max": "SW", "min_len": 2, "max_len": 2}` | `{"count": 0, "nulls": 0, "distinct": 0}` |
| premium_amount | `{"count": 1500, "nulls": 0, "distinct": 1497, "min": "305.91", "max": "5998.62", "sum": "4682700.2"}` | `{"count": 0, "nulls": 0, "distinct": 0}` |
| effective_date | `{"count": 1500, "nulls": 0, "distinct": 30, "min": "2026-09-01", "max": "2026-09-30", "min_len": 10, "max_len": 10}` | `{"count": 0, "nulls": 0, "distinct": 0}` |

## L4 sampled diffs

| Key | Column | Legacy | Snowflake |
|---|---|---|---|
| PL00100001   | (row) | present | missing |
| PL00100002   | (row) | present | missing |
| PL00100005   | (row) | present | missing |
| PL00100006   | (row) | present | missing |
| PL00100007   | (row) | present | missing |
| PL00100008   | (row) | present | missing |
| PL00100011   | (row) | present | missing |
| PL00100012   | (row) | present | missing |
| PL00100013   | (row) | present | missing |
| PL00100015   | (row) | present | missing |
| PL00100016   | (row) | present | missing |
| PL00100017   | (row) | present | missing |
| PL00100020   | (row) | present | missing |
| PL00100021   | (row) | present | missing |
| PL00100023   | (row) | present | missing |
| PL00100024   | (row) | present | missing |
| PL00100026   | (row) | present | missing |
| PL00100027   | (row) | present | missing |
| PL00100028   | (row) | present | missing |
| PL00100029   | (row) | present | missing |
| PL00100030   | (row) | present | missing |
| PL00100031   | (row) | present | missing |
| PL00100032   | (row) | present | missing |
| PL00100033   | (row) | present | missing |
| PL00100034   | (row) | present | missing |
