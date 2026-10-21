# Parity: producer_dashboard.qvs.RegionClaimRate (run-2)

Run at 2026-10-21 21:09 UTC.

L1 green (4 vs 4), L2 red (1 columns drift), L3 red (0.0% hash match), L4 red (4 sampled diffs)

| Level | Result | Detail |
|---|---|---|
| L1 counts | green | legacy 4, snowflake 4 |
| L2 profiles | red | drift in: claim_rate_pct |
| L3 row hash | red | 0/4 keys match (0.0%) |
| L4 samples | red | 4 diffs sampled |

## L2 drift

| Column | Legacy | Snowflake |
|---|---|---|
| claim_rate_pct | `{"count": 4, "nulls": 0, "distinct": 2, "min": "16", "max": "17", "sum": "67"}` | `{"count": 4, "nulls": 0, "distinct": 4, "min": "16.474", "max": "17.6589", "sum": "69.319"}` |

## L4 sampled diffs

| Key | Column | Legacy | Snowflake |
|---|---|---|---|
| MW | claim_rate_pct | `17` | `17.6303` |
| NE | claim_rate_pct | `17` | `17.6589` |
| SE | claim_rate_pct | `16` | `16.474` |
| SW | claim_rate_pct | `17` | `17.5558` |
