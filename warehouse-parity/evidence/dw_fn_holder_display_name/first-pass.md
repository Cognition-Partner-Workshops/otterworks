# Parity: dw.fn_holder_display_name (first-pass)

Run at 2026-10-21 21:09 UTC.

L1 green (2000 vs 2000), L2 red (1 columns drift), L3 red (53.05% hash match), L4 red (25 sampled diffs)

| Level | Result | Detail |
|---|---|---|
| L1 counts | green | legacy 2000, snowflake 2000 |
| L2 profiles | red | drift in: display_name |
| L3 row hash | red | 1061/2000 keys match (53.05%) |
| L4 samples | red | 25 diffs sampled |

## L2 drift

| Column | Legacy | Snowflake |
|---|---|---|
| display_name | `{"count": 2000, "nulls": 0, "distinct": 1360, "min": "Abbott, Ana", "max": "Thompson, Tara Omar", "min_len": 9, "max_len": 22}` | `{"count": 2000, "nulls": 939, "distinct": 994, "min": "Abbott, Ana Elena", "max": "Thompson, Tara Omar", "min_len": 13, "max_len": 22}` |

## L4 sampled diffs

| Key | Column | Legacy | Snowflake |
|---|---|---|---|
| PL00100000 | display_name | `Duarte, Sam` | `\N` |
| PL00100001 | display_name | `Baker, Elena` | `\N` |
| PL00100003 | display_name | `Duarte, Kai` | `\N` |
| PL00100005 | display_name | `Sato, Elena` | `\N` |
| PL00100007 | display_name | `Abbott, Elena` | `\N` |
| PL00100009 | display_name | `Okafor, Grace` | `\N` |
| PL00100011 | display_name | `Okafor, Priya` | `\N` |
| PL00100013 | display_name | `Gupta, Ana` | `\N` |
| PL00100015 | display_name | `Nakamura, Priya` | `\N` |
| PL00100016 | display_name | `Fischer, Hiro` | `\N` |
| PL00100017 | display_name | `Jensen, Ana` | `\N` |
| PL00100018 | display_name | `Hale, Nora` | `\N` |
| PL00100020 | display_name | `Patel, Hiro` | `\N` |
| PL00100021 | display_name | `Thompson, Chloe` | `\N` |
| PL00100023 | display_name | `Sato, Ana` | `\N` |
| PL00100024 | display_name | `Jensen, Mateo` | `\N` |
| PL00100026 | display_name | `Rossi, Ben` | `\N` |
| PL00100029 | display_name | `Jensen, Ana` | `\N` |
| PL00100032 | display_name | `Moreau, Isla` | `\N` |
| PL00100033 | display_name | `Quintero, Mateo` | `\N` |
| PL00100034 | display_name | `Rossi, Tara` | `\N` |
| PL00100036 | display_name | `Lindqvist, Dev` | `\N` |
| PL00100038 | display_name | `Jensen, Tara` | `\N` |
| PL00100039 | display_name | `Ibarra, Kai` | `\N` |
| PL00100041 | display_name | `Hale, Isla` | `\N` |
