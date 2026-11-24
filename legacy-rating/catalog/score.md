# Rating catalog score

Counts below refer to [the final rule entries](rules.md), not source entry counts or cross-check observations. The four statuses are disjoint and add up to found. Missed overlaps those statuses: the condition was absent from both phase-one extracts and found during cross-check. R99 comes from the later #3387 table change, not from that cross-check.

| Scope | Found | From-table | Proven | Amber | Unproven | Missed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Shared legacy conditions | 83 | 35 | 34 | 3 | 11 | 24 |
| COBOL only | 2 | 0 | 0 | 0 | 2 | 0 |
| Pharo only | 14 | 0 | 0 | 8 | 6 | 1 |
| **Unique merged total** | **99** | **35** | **34** | **11** | **19** | **25** |

### Per-stack view

Each stack includes the shared conditions plus its own conditions; the two rows therefore cannot be added together.

| Scope | Found | From-table | Proven | Amber | Unproven | Missed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| COBOL | 85 | 35 | 34 | 3 | 13 | 24 |
| Pharo | 97 | 35 | 34 | 11 | 17 | 25 |

Phase-one intake: 48 COBOL and 65 Pharo entries. The COBOL cross-check reviewed the same 48; the Pharo cross-check supplied 25 new entries (R-ST-66–90). The extract-to-catalog mapping shows how those inputs became the merged counts.

### Table row coverage

Counts are physical data rows, excluding header comments. Both stacks select the same rows; the shared total is not doubled. Eligibility row 6 is inferred from keys and control flow, not distinguished by the output.

| Table | Rows | COBOL reached | COBOL unused | Pharo reached | Pharo unused |
| --- | ---: | ---: | ---: | ---: | ---: |
| `tables/class-factors.dat` | 14 | 11 | 3 | 11 | 3 |
| `tables/line-eligibility.dat` | 4 | 4 | 0 | 4 | 0 |
| `tables/territory-factors.dat` | 14 | 13 | 1 | 13 | 1 |
| `tables/overrides.dat` | 3 | 3 | 0 | 3 | 0 |
| `tables/minimum-premium.dat` | 6 | 5 | 1 | 5 | 1 |
| **Total** | **41** | **36** | **5** | **36** | **5** |

### Owner decisions

- **R43 — PR/030 duration:** the recorded statement has no end date for the 1.250 factor, but #3387 ends that row on June 30. R43 is amber; R99 records the separately proven 1.300 row that starts July 1.
- **R82 — minimum order:** should the floor apply before or after schedule and multi-policy adjustments? The two legacy stacks choose the same row, but can produce different modified amounts and minimum flags.
- **R84 and Pharo-only amber entries — endorsements:** should optional Pharo quote charges be included in the final total, and should its guards, rounding, and cap be retained? COBOL does not charge for them.
- **Florida property wind:** COBOL has a source path but no PR/WND row; the shipped corpus cannot show a non-neutral amount. No disagreement is asserted for current tables.
