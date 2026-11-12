# Live Oracle characterization report

UTC: 2026-11-12T16:04:40.126842+00:00
Container: `otterworks-insurance-rules-insurance-oracle-1`
Image: `sha256:f988b0c04c4c386cd306a2a914c0d7a9702d83acc31b064a28ad8eb6278a8fba`

Green = no identified contradiction; amber = owner decision required, NOT a failed test or approval.
PASS means the existing database behavior was observed, not that it matches the specification.
These tests mutate only a disposable fixture. Use a fresh namespace; do not run on a shared database.

| Rule | Color | Test | Result | Observations |
|---|---|---|---|---|
| CP-001 | green | T-CP-001 | PASS | all five product/line mappings; only WL-PAR and FIA-7 tiered in fixture; TERM-20 default=15; at least one assertion executed |
| CP-002 | green | T-CP-002 | PASS | default ACTIVE; expected error -2290; actual -2290; at least one assertion executed |
| CP-003 | green | T-CP-003 | PASS | expected error -1; actual -1; expected error -1; actual -1; expected error -1; actual -1; expected error -2291; actual -2291; expected error -2291; actual -2291; expected error -2291; actual -2291; expected error -2291; actual -2291; expected error -2291; actual -2291; at least one assertion executed |
| CP-004 | green | T-CP-004 | PASS | premium stored=100.13; default IN_FORCE; expected error -2290; actual -2290; expected error -2290; actual -2290; at least one assertion executed |
| CP-005 | green | T-CP-005 | PASS | expected error -20001; actual -20001; expected error -20001; actual -20001; expected error -20001; actual -20001; expected error -20001; actual -20001; upper bound 50 accepted; at least one assertion executed |
| CP-006 | green | T-CP-006 | PASS | expected error -20004; actual -20004; expected error -20002; actual -20002; expected error -20003; actual -20003; expected error -20003; actual -20003; active named agent accepted; at least one assertion executed |
| CP-007 | green | T-CP-007 | PASS | same-day rate ID preserved; same-day percentage and author replaced; at least one assertion executed |
| CP-008 | green | T-CP-008 | PASS | old default retained and closed 2024-12-31; agent scope unchanged; at least one assertion executed |
| CP-009 | green | T-CP-009 | PASS | expected error -1; actual -1; expected error -2290; actual -2290; failed backdates preserve open rate; at least one assertion executed |
| CP-010 | green | T-CP-010 | PASS | end date inclusive; expected error -20007; actual -20007; at least one assertion executed |
| CP-011 | green | T-CP-011 | PASS | expected error -20005; actual -20005; expected error -20006; actual -20006; expected error -20006; actual -20006; lapsed policy split update accepted; at least one assertion executed |
| CP-012 | green | T-CP-012 | PASS | expected error -20006; actual -20006; expected error -20006; actual -20006; at least one assertion executed |
| CP-013 | green | T-CP-013 | PASS | expected error -20006; actual -20006; expected error -20006; actual -20006; expected error -20006; actual -20006; expected error -20003; actual -20003; expected error -20002; actual -20002; at least one assertion executed |
| CP-014 | green | T-CP-014 | PASS | expected error -20006; actual -20006; expected error -20006; actual -20006; invalid replacement left two splits totaling 100; at least one assertion executed |
| CP-015 | green | T-CP-015 | PASS | override applies at start; default before override start; default without override; at least one assertion executed |
| CP-016 | green | T-CP-016 | PASS | latest overlapping closed history wins; expected error -20007; actual -20007; at least one assertion executed |
| CP-017 | green | T-CP-017 | PASS | commission=12; at least one assertion executed |
| CP-018 | amber | T-CP-018 | PASS | 49999.99 => T1; 50000 => T2; 50000.01 => T2; at least one assertion executed |
| CP-019 | amber | T-CP-019 | PASS | initial T1; premium adjustment changes tier to T2; at least one assertion executed |
| CP-020 | green | T-CP-020 | PASS | WL T1 old=45; WL T1 new=40; WL T2=30; FIA T1=6; FIA T2=4.5; at least one assertion executed |
| CP-021 | amber | T-CP-021 | PASS | July 1 uses OLD 45 not spec 40; expected error -20007; actual -20007; at least one assertion executed |
| CP-022 | green | T-CP-022 | PASS | commission=45; ledger rate ID references 49% flat override, paid schedule=45%; expected error -20007; actual -20007; at least one assertion executed |
| CP-023 | green | T-CP-023 | PASS | expected error -20005; actual -20005; expected error -20008; actual -20008; expected error -20008; actual -20008; expected error -20006; actual -20006; at least one assertion executed |
| CP-024 | green | T-CP-024 | PASS | commission=20; at least one assertion executed |
| CP-025 | green | T-CP-025 | PASS | two independently rounded 7.50 rows; no residual-cent allocation; positive half-cent rounds up; at least one assertion executed |
| CP-026 | green | T-CP-026 | PASS | one commission 15 plus preserved chargeback -2; at least one assertion executed |
| CP-027 | green | T-CP-027 | PASS | commission=15; commission=7.5; at least one assertion executed |
| CP-028 | green | T-CP-028 | PASS | commission=15; at least one assertion executed |
| CP-029 | green | T-CP-029 | PASS | commission=1500; commission=1000; commission=0; at least one assertion executed |
| CP-030 | green | T-CP-030 | PASS | commission=0; commission=1500; at least one assertion executed |
| CP-031 | amber | T-CP-031 | PASS | commission=150; commission=1000; commission=0; direct update permits aggregate 4000 above cap; at least one assertion executed |
| CP-032 | green | T-CP-032 | PASS | expected error -20005; actual -20005; lapse persisted; expected error -20008; actual -20008; at least one assertion executed |
| CP-033 | amber | T-CP-033 | PASS | month 7 reverses full 120; spec would reverse 60; exactly 12 months no chargeback; month 5 reverses full 120; at least one assertion executed |
| CP-034 | green | T-CP-034 | PASS | agent1 paid 18 reversed in supplied May; agent2 paid 12 reversed; at least one assertion executed |
| CP-035 | amber | T-CP-035 | PASS | pre-issue lapse reverses future August commission; at least one assertion executed |
| CP-036 | amber | T-CP-036 | PASS | expected error -2290; actual -2290; cancel generated no chargeback; no surrender entrypoint; at least one assertion executed |
| CP-037 | green | T-CP-037 | PASS | RATE_UPSERT/RATE_END/SPLIT_SET/COMMISSION_CALC/POLICY_LAPSE audited; at least one assertion executed |
| CP-038 | green | T-CP-038 | PASS | expected error -20006; actual -20006; failed package call rolled back caller update; success committed caller update; at least one assertion executed |
| CP-039 | green | T-CP-039 | PASS | expected error -20006; actual -20006; commission=15; no failed calculation audit; at least one assertion executed |
| CP-040 | green | T-CP-040 | PASS | expected error -2290; actual -2290; expected error -2290; actual -2290; expected error -1; actual -1; at least one assertion executed |
| CP-041 | green | T-CP-041 | PASS | suspended agent loaded; current product description loaded; existing dimension description refreshed; at least one assertion executed |
| CP-042 | green | T-CP-042 | PASS | August 2025 => year2025 quarter3; NULL period loaded both January and February; at least one assertion executed |
| CP-043 | green | T-CP-043 | PASS | all copied money/premium/splits reconcile, including chargebacks and capped amounts; chargebacks loaded separately; at least one assertion executed |
| CP-044 | green | T-CP-044 | PASS | rerun count unchanged; merged count includes matches=33; at least one assertion executed |
| CP-045 | amber | T-CP-045 | PASS | DW 50000=T1; OLTP 50000=T2; at least one assertion executed |
| CP-046 | amber | T-CP-046 | PASS | DW T1 versus null OLTP tier on chargeback; at least one assertion executed |
| CP-047 | amber | T-CP-047 | PASS | initial source fact present; at least one assertion executed |
| CP-048 | green | T-CP-048 | PASS | old agent3 source row deleted; at least one assertion executed |
| CP-049 | amber | T-CP-049 | PASS | warehouse keeps old 15 plus new 15; ledger has only new-agent 15; at least one assertion executed |
| CP-050 | green | T-CP-050 | PASS | summary signed totals and fact-row counts match aggregation; at least one assertion executed |
| CP-051 | green | T-CP-051 | PASS | summary refresh mode DEMAND; explicit refresh was recorded; at least one assertion executed |
| CP-052 | green | T-CP-052 | PASS | expected error -20007; actual -20007; at least one assertion executed |
| CP-053 | amber | T-CP-053 | PASS | commission=120; no separate premium basis fields; at least one assertion executed |
| CP-054 | green | T-CP-054 | PASS | expected error -2290; actual -2290; COMMERCIAL allowed without commissioned schedule; at least one assertion executed |
| CP-055 | green | T-CP-055 | PASS | default entry type; expected error -2290; actual -2290; expected error -1; actual -1; at least one assertion executed |
| CP-056 | green | T-CP-056 | PASS | expected error -1400; actual -1400; missing audit actor rolls back new ledger rows; expected error -1407; actual -1407; null created_by update preserved prior rate; at least one assertion executed |
| CP-057 | green | T-CP-057 | PASS | NULL end date leaves rate open; RATE_END audited despite still-open rate; at least one assertion executed |
| CP-058 | green | T-CP-058 | PASS | no paid rows, no reversal; unpaid policy lapsed; at least one assertion executed |
| CP-059 | amber | T-CP-059 | PASS | commission=900; at least one assertion executed |
| CP-060 | amber | T-CP-060 | PASS | accepted input total100 persisted100.01; at least one assertion executed |
| CP-061 | amber | T-CP-061 | PASS | commission=15; two accepted August spellings pay3000 across separate cap buckets; at least one assertion executed |
| CP-062 | green | T-CP-062 | PASS | commission=10; at least one assertion executed |
| CP-063 | amber | T-CP-063 | PASS | DW still TERM-20 but updated to HOME amount10; source product HOME-PLUS; at least one assertion executed |
| CP-064 | amber | T-CP-064 | PASS | expected error -1; actual -1; expected error -1; actual -1; second historical closure fails; current rate preserved; at least one assertion executed |
| CP-065 | amber | T-CP-065 | PASS | expected error -4091; actual -4091; bulk statement rolled back; at least one assertion executed |

65/65 PASS; 18 amber rules; 12 owner decisions; 0 failed tests

Source and test SHA-256 fingerprints and full SQL*Plus logs are in the JSON and per-test files beside this report.
