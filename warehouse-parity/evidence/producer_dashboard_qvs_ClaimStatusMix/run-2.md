# Parity: producer_dashboard.qvs.ClaimStatusMix (run-2)

Run at 2026-10-21 21:09 UTC.

L1 green (5 vs 5), L2 red (1 columns drift), L3 red (0.0% hash match), L4 red (5 sampled diffs)

| Level | Result | Detail |
|---|---|---|
| L1 counts | green | legacy 5, snowflake 5 |
| L2 profiles | red | drift in: share_pct |
| L3 row hash | red | 0/5 keys match (0.0%) |
| L4 samples | red | 5 diffs sampled |

## L2 drift

| Column | Legacy | Snowflake |
|---|---|---|
| share_pct | `{"count": 5, "nulls": 0, "distinct": 4, "min": "18", "max": "21", "sum": "97"}` | `{"count": 5, "nulls": 0, "distinct": 5, "min": "18.8667", "max": "21.5333", "sum": "100"}` |

## L4 sampled diffs

| Key | Column | Legacy | Snowflake |
|---|---|---|---|
| CLSD | share_pct | `19` | `19.4` |
| DENY | share_pct | `19` | `19.2333` |
| OPEN | share_pct | `21` | `21.5333` |
| REOP | share_pct | `18` | `18.8667` |
| SUBR | share_pct | `20` | `20.9667` |
