# Parity: dw.v_policy_audit (first-pass)

Run at 2026-10-21 21:31 UTC.

L1 green (2705 vs 2705), L2 red (1 columns drift), L3 red (0.0% hash match), L4 red (25 sampled diffs)

| Level | Result | Detail |
|---|---|---|
| L1 counts | green | legacy 2705, snowflake 2705 |
| L2 profiles | red | drift in: event_weekday |
| L3 row hash | red | 0/4954 keys match (0.0%) |
| L4 samples | red | 25 diffs sampled |

## L2 drift

| Column | Legacy | Snowflake |
|---|---|---|
| event_weekday | `{"count": 2705, "nulls": 0, "distinct": 7, "min": "1", "max": "7", "sum": "10732"}` | `{"count": 2705, "nulls": 0, "distinct": 7, "min": "0", "max": "6", "sum": "8027"}` |

## L4 sampled diffs

| Key | Column | Legacy | Snowflake |
|---|---|---|---|
| PL00100003/5 | (row) | missing | present |
| PL00100003/6 | last_event_at | `2026-09-11 21:12:41.897` | `2026-09-26 21:23:50.563` |
| PL00100003/7 | (row) | present | missing |
| PL00100004/2 | (row) | missing | present |
| PL00100004/3 | last_event_at | `2026-09-01 13:53:22.154` | `2026-09-16 03:27:35.478` |
| PL00100004/4 | (row) | present | missing |
| PL00100006/4 | (row) | missing | present |
| PL00100006/5 | last_event_at | `2026-09-17 12:10:46.652` | `2026-09-04 14:56:32.371` |
| PL00100006/6 | (row) | present | missing |
| PL00100007/3 | (row) | missing | present |
| PL00100007/4 | last_event_at | `2026-09-02 00:33:19.096` | `2026-09-24 19:23:58.799` |
| PL00100007/5 | (row) | present | missing |
| PL00100008/5 | (row) | missing | present |
| PL00100008/6 | (row) | present | missing |
| PL00100009/0 | (row) | missing | present |
| PL00100009/1 | (row) | present | missing |
| PL00100009/2 | (row) | missing | present |
| PL00100009/3 | last_event_at | `2026-09-22 16:40:48.692` | `2026-09-16 08:02:17.231` |
| PL00100009/4 | (row) | present | missing |
| PL00100010/6 | (row) | missing | present |
| PL00100010/7 | (row) | present | missing |
| PL00100011/0 | (row) | missing | present |
| PL00100011/1 | event_count | `1` | `2` |
| PL00100011/1 | last_event_at | `2026-09-27 22:26:54.030` | `2026-09-14 02:42:56.667` |
| PL00100011/2 | (row) | present | missing |
| PL00100011/5 | (row) | missing | present |
