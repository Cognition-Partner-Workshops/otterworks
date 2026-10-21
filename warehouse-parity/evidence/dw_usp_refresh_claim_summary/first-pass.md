# Parity: dw.usp_refresh_claim_summary (first-pass)

Run at 2026-10-21 21:32 UTC.

L1 red (1552 vs 1037), L2 red (5 columns drift), L3 red (31.89% hash match), L4 red (25 sampled diffs)

| Level | Result | Detail |
|---|---|---|
| L1 counts | red | legacy 1552, snowflake 1037 |
| L2 profiles | red | drift in: policy_number, product_code, claim_count, total_claim_amount, last_loss_date |
| L3 row hash | red | 495/1552 keys match (31.89%) |
| L4 samples | red | 25 diffs sampled |

## L2 drift

| Column | Legacy | Snowflake |
|---|---|---|
| policy_number | `{"count": 1552, "nulls": 0, "distinct": 1552, "min": "PL00100000", "max": "PL00101999", "min_len": 10, "max_len": 10}` | `{"count": 1037, "nulls": 0, "distinct": 1037, "min": "PL00100000", "max": "PL00101995", "min_len": 10, "max_len": 10}` |
| product_code | `{"count": 1552, "nulls": 0, "distinct": 5, "min": "AUTO", "max": "UMBR", "min_len": 4, "max_len": 4}` | `{"count": 1037, "nulls": 0, "distinct": 5, "min": "AUTO", "max": "UMBR", "min_len": 4, "max_len": 4}` |
| claim_count | `{"count": 1552, "nulls": 0, "distinct": 7, "min": "1", "max": "8", "sum": "3000"}` | `{"count": 1037, "nulls": 0, "distinct": 5, "min": "1", "max": "5", "sum": "1499"}` |
| total_claim_amount | `{"count": 1552, "nulls": 0, "distinct": 1552, "min": "125.08", "max": "106905.36", "sum": "37191072.48"}` | `{"count": 1037, "nulls": 0, "distinct": 1036, "min": "125.08", "max": "100877.79", "sum": "18429999.66"}` |
| last_loss_date | `{"count": 1552, "nulls": 0, "distinct": 30, "min": "2026-09-01", "max": "2026-09-30", "min_len": 10, "max_len": 10}` | `{"count": 1037, "nulls": 0, "distinct": 30, "min": "2026-09-01", "max": "2026-09-30", "min_len": 10, "max_len": 10}` |

## L4 sampled diffs

| Key | Column | Legacy | Snowflake |
|---|---|---|---|
| PL00100001 | claim_count | `3` | `1` |
| PL00100001 | total_claim_amount | `38329.62` | `17060.74` |
| PL00100001 | last_loss_date | `2026-09-28` | `2026-09-24` |
| PL00100002 | (row) | present | missing |
| PL00100003 | claim_count | `3` | `2` |
| PL00100003 | total_claim_amount | `30159.86` | `25971.65` |
| PL00100004 | claim_count | `3` | `2` |
| PL00100004 | total_claim_amount | `30213.34` | `16561.3` |
| PL00100005 | (row) | present | missing |
| PL00100006 | (row) | present | missing |
| PL00100008 | (row) | present | missing |
| PL00100010 | (row) | present | missing |
| PL00100013 | claim_count | `2` | `1` |
| PL00100013 | total_claim_amount | `38128.02` | `16628.84` |
| PL00100013 | last_loss_date | `2026-09-24` | `2026-09-17` |
| PL00100016 | (row) | present | missing |
| PL00100019 | claim_count | `6` | `2` |
| PL00100019 | total_claim_amount | `70147.22` | `14783.07` |
| PL00100022 | (row) | present | missing |
| PL00100023 | claim_count | `2` | `1` |
| PL00100023 | total_claim_amount | `32615.46` | `19954.43` |
| PL00100023 | last_loss_date | `2026-09-14` | `2026-09-13` |
| PL00100027 | (row) | present | missing |
| PL00100028 | claim_count | `2` | `1` |
| PL00100028 | total_claim_amount | `27585.28` | `22689.8` |
| PL00100028 | last_loss_date | `2026-09-28` | `2026-09-22` |
| PL00100030 | claim_count | `4` | `2` |
| PL00100030 | total_claim_amount | `32892.6` | `5552.22` |
| PL00100030 | last_loss_date | `2026-09-30` | `2026-09-25` |
| PL00100031 | claim_count | `3` | `2` |
| PL00100031 | total_claim_amount | `23209.58` | `15755` |
| PL00100031 | last_loss_date | `2026-09-11` | `2026-09-06` |
| PL00100032 | (row) | present | missing |
| PL00100034 | claim_count | `3` | `2` |
| PL00100034 | total_claim_amount | `26061.43` | `12927.87` |
| PL00100035 | claim_count | `2` | `1` |
| PL00100035 | total_claim_amount | `28164.93` | `9358.19` |
| PL00100035 | last_loss_date | `2026-09-30` | `2026-09-20` |
| PL00100037 | claim_count | `2` | `1` |
| PL00100037 | total_claim_amount | `10370.86` | `3459.3` |
| PL00100037 | last_loss_date | `2026-09-15` | `2026-09-14` |
| PL00100038 | claim_count | `2` | `1` |
| PL00100038 | total_claim_amount | `21042.16` | `4555.95` |
| PL00100039 | (row) | present | missing |
| PL00100040 | claim_count | `2` | `1` |
| PL00100040 | total_claim_amount | `25209.95` | `20540.14` |
| PL00100041 | (row) | present | missing |
