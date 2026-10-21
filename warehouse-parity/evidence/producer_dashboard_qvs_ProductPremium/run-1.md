# Parity: producer_dashboard.qvs.ProductPremium (run-1)

Run at 2026-10-21 21:09 UTC.

L1 red (5 vs 0), L2 red (4 columns drift), L3 red (0.0% hash match), L4 red (5 sampled diffs)

| Level | Result | Detail |
|---|---|---|
| L1 counts | red | legacy 5, snowflake 0 |
| L2 profiles | red | drift in: product_code, policy_count, written_premium, avg_premium |
| L3 row hash | red | 0/5 keys match (0.0%) |
| L4 samples | red | 5 diffs sampled |

## L2 drift

| Column | Legacy | Snowflake |
|---|---|---|
| product_code | `{"count": 5, "nulls": 0, "distinct": 5, "min": "AUTO", "max": "UMBR", "min_len": 4, "max_len": 4}` | `{"count": 0, "nulls": 0, "distinct": 0}` |
| policy_count | `{"count": 5, "nulls": 0, "distinct": 5, "min": "281", "max": "324", "sum": "1500"}` | `{"count": 0, "nulls": 0, "distinct": 0}` |
| written_premium | `{"count": 5, "nulls": 0, "distinct": 5, "min": "855609.89", "max": "1030161.96", "sum": "4682700.2"}` | `{"count": 0, "nulls": 0, "distinct": 0}` |
| avg_premium | `{"count": 5, "nulls": 0, "distinct": 5, "min": "3044.88", "max": "3248.88", "sum": "15595.06"}` | `{"count": 0, "nulls": 0, "distinct": 0}` |

## L4 sampled diffs

| Key | Column | Legacy | Snowflake |
|---|---|---|---|
| AUTO | (row) | present | missing |
| BOAT | (row) | present | missing |
| HOME | (row) | present | missing |
| RENT | (row) | present | missing |
| UMBR | (row) | present | missing |
