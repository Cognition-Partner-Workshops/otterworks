# Parity: dw.v_claim_audit (first-pass)

Run at 2026-10-21 21:31 UTC.

L1 green (4977 vs 4977), L2 red (1 columns drift), L3 red (0.0% hash match), L4 red (25 sampled diffs)

| Level | Result | Detail |
|---|---|---|
| L1 counts | green | legacy 4977, snowflake 4977 |
| L2 profiles | red | drift in: event_weekday |
| L3 row hash | red | 0/4977 keys match (0.0%) |
| L4 samples | red | 25 diffs sampled |

## L2 drift

| Column | Legacy | Snowflake |
|---|---|---|
| event_weekday | `{"count": 4977, "nulls": 0, "distinct": 7, "min": "1", "max": "7", "sum": "19502"}` | `{"count": 4977, "nulls": 0, "distinct": 7, "min": "0", "max": "6", "sum": "14525"}` |

## L4 sampled diffs

| Key | Column | Legacy | Snowflake |
|---|---|---|---|
| 1/note_added/2026-09-10 | event_weekday | `5` | `4` |
| 1/note_added/2026-09-11 | event_weekday | `6` | `5` |
| 10/created/2026-09-13 | event_weekday | `1` | `0` |
| 10/created/2026-09-19 | event_weekday | `7` | `6` |
| 10/reserve_change/2026-09-16 | event_weekday | `4` | `3` |
| 1000/reserve_change/2026-09-25 | event_weekday | `6` | `5` |
| 1000/reserve_change/2026-09-26 | event_weekday | `7` | `6` |
| 1001/note_added/2026-09-26 | event_weekday | `7` | `6` |
| 1004/note_added/2026-09-06 | event_weekday | `1` | `0` |
| 1005/closed/2026-09-07 | event_weekday | `2` | `1` |
| 1005/note_added/2026-09-27 | event_weekday | `1` | `0` |
| 1006/assigned/2026-09-03 | event_weekday | `5` | `4` |
| 1006/reserve_change/2026-09-02 | event_weekday | `4` | `3` |
| 1006/reserve_change/2026-09-11 | event_weekday | `6` | `5` |
| 1008/reserve_change/2026-09-03 | event_weekday | `5` | `4` |
| 1009/closed/2026-09-11 | event_weekday | `6` | `5` |
| 1009/created/2026-09-28 | event_weekday | `2` | `1` |
| 1009/note_added/2026-09-07 | event_weekday | `2` | `1` |
| 101/closed/2026-09-24 | event_weekday | `5` | `4` |
| 101/note_added/2026-09-09 | event_weekday | `4` | `3` |
| 1010/note_added/2026-09-06 | event_weekday | `1` | `0` |
| 1011/reserve_change/2026-09-18 | event_weekday | `6` | `5` |
| 1012/assigned/2026-09-23 | event_weekday | `4` | `3` |
| 1012/assigned/2026-09-24 | event_weekday | `5` | `4` |
| 1012/assigned/2026-09-25 | event_weekday | `6` | `5` |
