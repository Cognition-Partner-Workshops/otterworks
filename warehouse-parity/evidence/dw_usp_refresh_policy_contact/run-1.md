# Parity: dw.usp_refresh_policy_contact (run-1)

Run at 2026-10-21 21:32 UTC.

L1 green (2000 vs 2000), L2 red (1 columns drift), L3 red (86.7% hash match), L4 red (25 sampled diffs)

| Level | Result | Detail |
|---|---|---|
| L1 counts | green | legacy 2000, snowflake 2000 |
| L2 profiles | red | drift in: contact_label |
| L3 row hash | red | 1734/2000 keys match (86.7%) |
| L4 samples | red | 25 diffs sampled |

## L2 drift

| Column | Legacy | Snowflake |
|---|---|---|
| contact_label | `{"count": 2000, "nulls": 126, "distinct": 13, "min": "+1 (555) 1", "max": "Work", "min_len": 4, "max_len": 10}` | `{"count": 2000, "nulls": 126, "distinct": 270, "min": "+1 (555) 107-2303", "max": "Work", "min_len": 4, "max_len": 25}` |

## L4 sampled diffs

| Key | Column | Legacy | Snowflake |
|---|---|---|---|
| PL00100018 | contact_label | `+1 (555) 3` | `+1 (555) 309-2384` |
| PL00100022 | contact_label | `+1 (555) 6` | `+1 (555) 664-8614` |
| PL00100059 | contact_label | `+1 (555) 7` | `+1 (555) 773-4117 ext 194` |
| PL00100062 | contact_label | `+1 (555) 1` | `+1 (555) 126-2993 ext 591` |
| PL00100078 | contact_label | `+1 (555) 7` | `+1 (555) 773-6522 ext 657` |
| PL00100080 | contact_label | `+1 (555) 9` | `+1 (555) 933-7668` |
| PL00100095 | contact_label | `+1 (555) 7` | `+1 (555) 769-7540` |
| PL00100104 | contact_label | `+1 (555) 2` | `+1 (555) 258-9187 ext 199` |
| PL00100114 | contact_label | `+1 (555) 8` | `+1 (555) 894-3834` |
| PL00100116 | contact_label | `+1 (555) 1` | `+1 (555) 137-6382 ext 72` |
| PL00100126 | contact_label | `+1 (555) 1` | `+1 (555) 118-6972` |
| PL00100142 | contact_label | `+1 (555) 9` | `+1 (555) 988-8374` |
| PL00100156 | contact_label | `+1 (555) 1` | `+1 (555) 144-1947` |
| PL00100158 | contact_label | `+1 (555) 2` | `+1 (555) 212-5232` |
| PL00100178 | contact_label | `+1 (555) 2` | `+1 (555) 276-1137` |
| PL00100195 | contact_label | `+1 (555) 2` | `+1 (555) 286-8218` |
| PL00100201 | contact_label | `+1 (555) 4` | `+1 (555) 475-5068` |
| PL00100205 | contact_label | `+1 (555) 9` | `+1 (555) 996-8238 ext 327` |
| PL00100208 | contact_label | `+1 (555) 1` | `+1 (555) 179-2319` |
| PL00100222 | contact_label | `+1 (555) 9` | `+1 (555) 927-1457` |
| PL00100224 | contact_label | `+1 (555) 3` | `+1 (555) 365-4223` |
| PL00100226 | contact_label | `+1 (555) 7` | `+1 (555) 718-1542` |
| PL00100227 | contact_label | `+1 (555) 1` | `+1 (555) 164-5803` |
| PL00100239 | contact_label | `+1 (555) 5` | `+1 (555) 538-5888` |
| PL00100241 | contact_label | `+1 (555) 6` | `+1 (555) 696-1393` |
