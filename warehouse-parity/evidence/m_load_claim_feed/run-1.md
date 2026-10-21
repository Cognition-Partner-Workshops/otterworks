# Parity: m_load_claim_feed (run-1)

Run at 2026-10-21 21:10 UTC.

L1 green (3000 vs 3000), L2 red (1 columns drift), L3 red (18.87% hash match), L4 red (25 sampled diffs)

| Level | Result | Detail |
|---|---|---|
| L1 counts | green | legacy 3000, snowflake 3000 |
| L2 profiles | red | drift in: reopen_date |
| L3 row hash | red | 566/3000 keys match (18.87%) |
| L4 samples | red | 25 diffs sampled |

## L2 drift

| Column | Legacy | Snowflake |
|---|---|---|
| reopen_date | `{"count": 3000, "nulls": 0, "distinct": 22, "min": "1900-01-01", "max": "2026-09-30", "min_len": 10, "max_len": 10}` | `{"count": 3000, "nulls": 2434, "distinct": 21, "min": "2026-09-10", "max": "2026-09-30", "min_len": 10, "max_len": 10}` |

## L4 sampled diffs

| Key | Column | Legacy | Snowflake |
|---|---|---|---|
| 1 | reopen_date | `1900-01-01` | `\N` |
| 100 | reopen_date | `1900-01-01` | `\N` |
| 1000 | reopen_date | `1900-01-01` | `\N` |
| 1001 | reopen_date | `1900-01-01` | `\N` |
| 1002 | reopen_date | `1900-01-01` | `\N` |
| 1003 | reopen_date | `1900-01-01` | `\N` |
| 1004 | reopen_date | `1900-01-01` | `\N` |
| 1007 | reopen_date | `1900-01-01` | `\N` |
| 1008 | reopen_date | `1900-01-01` | `\N` |
| 1009 | reopen_date | `1900-01-01` | `\N` |
| 101 | reopen_date | `1900-01-01` | `\N` |
| 1010 | reopen_date | `1900-01-01` | `\N` |
| 1011 | reopen_date | `1900-01-01` | `\N` |
| 1012 | reopen_date | `1900-01-01` | `\N` |
| 1013 | reopen_date | `1900-01-01` | `\N` |
| 1014 | reopen_date | `1900-01-01` | `\N` |
| 1016 | reopen_date | `1900-01-01` | `\N` |
| 1017 | reopen_date | `1900-01-01` | `\N` |
| 1018 | reopen_date | `1900-01-01` | `\N` |
| 1019 | reopen_date | `1900-01-01` | `\N` |
| 102 | reopen_date | `1900-01-01` | `\N` |
| 1021 | reopen_date | `1900-01-01` | `\N` |
| 1024 | reopen_date | `1900-01-01` | `\N` |
| 1025 | reopen_date | `1900-01-01` | `\N` |
| 1026 | reopen_date | `1900-01-01` | `\N` |
