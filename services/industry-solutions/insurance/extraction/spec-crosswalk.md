# CP-114 Revision 3 — scanned specification crosswalk

Source: `../spec/cp114-commission-spec-scan.pdf`, three image-only pages, visually rendered and read in full. Header: Product and Commission Specification, Individual Life and Annuity — Agency Distribution, effective July 1, 2025, superseding Rev.2 (2019). Approval signature/date lines on p3 are blank: this is documentary intent, not evidence of current approval. The generator was not used as a substitute for reading the scan.

| Page / section | Read requirement | Catalog match | Reconciliation |
|---|---|---|---|
| p1 §1 Scope | Career agency products and writing-agent commissions | CP-001, CP-053 | No channel field/filter in database; owner must confirm fixture scope/upstream inputs (D9). No claim of channel eligibility enforcement. |
| p1 §2 Products | TERM-20 / 20-Year Term Life / Life / flat | CP-001 | Matches seed and absence of tier rows |
| p1 §2 Products | WL-PAR / Participating Whole Life / Life / tiered | CP-001, CP-017 | Matches seed; source detects tiering from schedule rows |
| p1 §2 Products | FIA-7 / 7-Year Fixed Indexed Annuity / Annuity / tiered | CP-001, CP-017 | Matches seed |
| p1 §2 Premium basis | Annualized planned premium; FIA single premium treated as annualized premium | CP-004, CP-053 | Amber D9: annual_premium used directly, no upstream mapping or separate basis fields to verify |
| p1 §3 Tier threshold | T1 under 50,000; T2 50,000 or more | CP-018, CP-045 | Amber D1: payment agrees, warehouse labels exactly 50,000 T1 |
| p1 §3 Tier immutability | Tier fixed at issue, unchanged after premium adjustments | CP-019, CP-046 | Amber D2: current premium is reread; no immutable issue-premium/tier snapshot |
| p1 §3 First-year language | Tiered products pay a first-year rate | CP-020, CP-028, CP-059 | Amber D10: no policy-year duration/renewal eligibility check; owner must define later-year entitlement |
| p2 §4 TERM-20 row | 15% from 2024-01-01 | CP-001, CP-015 | Matches flat seed, inclusive date selection |
| p2 §4 WL-PAR T1 rows | 45% 2020-01-01 through 2025-06-30, then 40% 2025-07-01 | CP-020, CP-021 | Numeric schedule matches; amber D3 on change/initial dates |
| p2 §4 WL-PAR T2 | 30% from 2020-01-01 | CP-020, CP-021 | Numeric schedule matches; strict initial date differs |
| p2 §4 FIA-7 T1/T2 | 6% / 4.5% from 2020-01-01 | CP-020, CP-021 | Numeric schedule matches; strict initial date differs |
| p2 §4.1 | Tier percentage based on issue date; new rate applies on effective date | CP-021, CP-022 | Issue-date selection matches; amber D3 on equality |
| p2 §4.2 | Paid monthly, one twelfth annualized premium × rate × agent split, rounded to cent | CP-025 | Matches per-agent formula; no residual-cent balancing |
| p2 §4.3 | Every sharing agent has a recorded split; total exactly 100% | CP-011/012/013/014/027 | Package validates replacement; direct table changes can bypass aggregate validation |
| p2 §5 | Agent/calendar month total across policies limited to 2,500 | CP-029, CP-031, CP-061, CP-065 | Initial inserts capped; amber D4 for update/recalculation lifecycle, noncanonical month buckets, and supported write paths |
| p2 §5 | Above-limit amounts not carried forward | CP-030 | Matches; no carry balance |
| p3 §6.1 event | Lapse OR surrender in first policy year | CP-032, CP-036 | Lapse supported; surrender absent, amber D7 |
| p3 §6.1 table row 1 | Months 1–6: 100% of paid commission | CP-033, CP-034 | Full reversal agrees inside early window |
| p3 §6.1 table row 2 | Months 7–12: 50% of paid commission | CP-033 | Amber D5: code reverses 100% while elapsed months <12 |
| p3 §6.1 table row 3 | Months 13 onward: no chargeback | CP-033 | None at >=12 elapsed months; owner must define ordinal-month boundary |
| p3 §6.2 booking | Book in month lapse is processed | CP-034, CP-035 | Amber D6 if supplied lapse date differs from processing date; only supplied date exists |
| p3 §6.2 sharing | Same agent proportion as commission paid | CP-034 | Matches paid-agent sums, not necessarily latest split |
| p3 §7 Approval | Agency Compensation, Product Actuarial, Commission Ops signatures/dates | sign-off.md | Blank on scan; all extracted rules remain pending approval |

AUTO and HOME are in the database but not in this life/annuity scan; absence of a scan clause is not a contradiction or permission to omit those rules. Warehouse current-dimension/stale-fact differences are separately documented even though the paper does not specify ETL internals.
